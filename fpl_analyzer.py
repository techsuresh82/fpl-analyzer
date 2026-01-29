#!/usr/bin/env python3
"""
FPL Team Analyzer - Weekly Transfer Recommendations
Analyzes your FPL team based on form, fixtures, expected points, price trends, and injuries
"""

import requests
import json
from datetime import datetime
from collections import defaultdict

class FPLAnalyzer:
    def __init__(self, team_id):
        self.team_id = team_id
        self.base_url = "https://fantasy.premierleague.com/api"
        self.bootstrap_data = None
        self.team_data = None
        self.fixtures_data = None
        
    def fetch_bootstrap_data(self):
        """Fetch general FPL data including all players"""
        response = requests.get(f"{self.base_url}/bootstrap-static/")
        response.raise_for_status()
        self.bootstrap_data = response.json()
        
    def fetch_team_data(self):
        """Fetch user's team data"""
        response = requests.get(f"{self.base_url}/entry/{self.team_id}/")
        response.raise_for_status()
        self.team_data = response.json()
        
        # Find current or next gameweek
        current_gw = None
        for event in self.bootstrap_data['events']:
            if event['is_current']:
                current_gw = event['id']
                break
            elif event['is_next']:
                current_gw = event['id']
                break
        
        # If no current or next, use the last finished gameweek + 1
        if current_gw is None:
            for event in reversed(self.bootstrap_data['events']):
                if event['finished']:
                    current_gw = event['id'] + 1
                    break
        
        # Fallback to gameweek 1 if nothing found
        if current_gw is None:
            current_gw = 1
        
        print(f"Fetching team data for Gameweek {current_gw}")
        picks_response = requests.get(f"{self.base_url}/entry/{self.team_id}/event/{current_gw}/picks/")
        picks_response.raise_for_status()
        self.team_picks = picks_response.json()
        
    def fetch_fixtures(self):
        """Fetch upcoming fixtures"""
        response = requests.get(f"{self.base_url}/fixtures/")
        response.raise_for_status()
        self.fixtures_data = response.json()
        
    def get_player_by_id(self, player_id):
        """Get player details from bootstrap data"""
        for player in self.bootstrap_data['elements']:
            if player['id'] == player_id:
                return player
        return None
    
    def get_team_name(self, team_id):
        """Get team name from ID"""
        for team in self.bootstrap_data['teams']:
            if team['id'] == team_id:
                return team['name']
        return "Unknown"
    
    def calculate_fixture_difficulty(self, player_id, num_fixtures=5):
        """Calculate upcoming fixture difficulty for a player"""
        player = self.get_player_by_id(player_id)
        if not player:
            return 0, []
        
        team_id = player['team']
        upcoming_fixtures = []
        
        for fixture in self.fixtures_data:
            if not fixture['finished']:
                if fixture['team_h'] == team_id:
                    upcoming_fixtures.append({
                        'opponent': self.get_team_name(fixture['team_a']),
                        'difficulty': fixture['team_h_difficulty'],
                        'home': True,
                        'event': fixture['event']
                    })
                elif fixture['team_a'] == team_id:
                    upcoming_fixtures.append({
                        'opponent': self.get_team_name(fixture['team_h']),
                        'difficulty': fixture['team_a_difficulty'],
                        'home': False,
                        'event': fixture['event']
                    })
        
        # Sort by gameweek and take next N fixtures
        upcoming_fixtures.sort(key=lambda x: x['event'])
        upcoming_fixtures = upcoming_fixtures[:num_fixtures]
        
        avg_difficulty = sum(f['difficulty'] for f in upcoming_fixtures) / len(upcoming_fixtures) if upcoming_fixtures else 0
        
        return avg_difficulty, upcoming_fixtures
    
    def analyze_player(self, player_id):
        """Comprehensive player analysis"""
        player = self.get_player_by_id(player_id)
        if not player:
            return None
        
        # Calculate metrics
        form = float(player['form']) if player['form'] else 0
        points_per_game = float(player['points_per_game']) if player['points_per_game'] else 0
        expected_points = float(player['ep_next']) if player['ep_next'] else 0
        price = player['now_cost'] / 10.0
        price_change = player['cost_change_start'] / 10.0
        selected_by = float(player['selected_by_percent'])
        
        # Injury/availability status
        availability = player['status']
        news = player['news']
        chance_of_playing = player['chance_of_playing_next_round']
        
        # Fixture difficulty
        avg_difficulty, fixtures = self.calculate_fixture_difficulty(player_id)
        
        # Calculate overall score (weighted)
        score = (
            form * 2.0 +
            points_per_game * 1.5 +
            expected_points * 1.0 +
            (5 - avg_difficulty) * 0.5  # Lower difficulty is better
        )
        
        # Penalize if injured or doubtful
        if availability != 'a':  # 'a' = available
            score *= 0.5
        if chance_of_playing and chance_of_playing < 75:
            score *= 0.7
        
        return {
            'id': player_id,
            'name': player['web_name'],
            'full_name': f"{player['first_name']} {player['second_name']}",
            'team': self.get_team_name(player['team']),
            'position': self.get_position_name(player['element_type']),
            'price': price,
            'price_change': price_change,
            'form': form,
            'points_per_game': points_per_game,
            'expected_points_next': expected_points,
            'total_points': player['total_points'],
            'selected_by': selected_by,
            'availability': availability,
            'news': news,
            'chance_of_playing': chance_of_playing,
            'avg_fixture_difficulty': avg_difficulty,
            'upcoming_fixtures': fixtures,
            'score': score
        }
    
    def get_position_name(self, element_type):
        """Convert element type to position name"""
        positions = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        return positions.get(element_type, 'Unknown')
    
    def get_current_team(self):
        """Get current team with analysis"""
        current_team = []
        for pick in self.team_picks['picks']:
            analysis = self.analyze_player(pick['element'])
            if analysis:
                analysis['is_captain'] = pick['is_captain']
                analysis['is_vice_captain'] = pick['is_vice_captain']
                analysis['multiplier'] = pick['multiplier']
                current_team.append(analysis)
        return current_team
    
    def find_transfer_targets(self, position=None, max_price=None):
        """Find potential transfer targets"""
        candidates = []
        
        for player in self.bootstrap_data['elements']:
            # Filter by position if specified
            if position and self.get_position_name(player['element_type']) != position:
                continue
            
            # Filter by price if specified
            if max_price and player['now_cost'] / 10.0 > max_price:
                continue
            
            # Only consider available players
            if player['status'] != 'a':
                continue
            
            analysis = self.analyze_player(player['id'])
            if analysis:
                candidates.append(analysis)
        
        # Sort by score (best first)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return candidates[:20]  # Top 20 candidates
    
    def generate_recommendations(self):
        """Generate transfer recommendations"""
        print("Fetching FPL data...")
        self.fetch_bootstrap_data()
        self.fetch_team_data()
        self.fetch_fixtures()
        
        print(f"Analyzing team: {self.team_data['name']}")
        print(f"Manager: {self.team_data['player_first_name']} {self.team_data['player_last_name']}")
        print(f"Team ID: {self.team_id}")
        
        current_team = self.get_current_team()
        
        # Sort by score to identify weak links
        current_team.sort(key=lambda x: x['score'])
        
        report = []
        report.append("# FPL WEEKLY ANALYSIS REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Manager: {self.team_data['player_first_name']} {self.team_data['player_last_name']}")
        report.append(f"Team: {self.team_data['name']}")
        report.append(f"Team ID: {self.team_id}")
        report.append("")
        
        # Team value and transfers
        report.append("## Team Status")
        report.append(f"- Team Value: £{self.team_data['last_deadline_value'] / 10.0:.1f}m")
        report.append(f"- In Bank: £{self.team_data['last_deadline_bank'] / 10.0:.1f}m")
        report.append(f"- Free Transfers: {self.team_picks['entry_history']['event_transfers_cost'] == 0 and 1 or 0}")
        report.append("")
        
        # Identify problem players
        report.append("## ⚠️ PLAYERS TO CONSIDER TRANSFERRING OUT")
        report.append("")
        
        problem_players = []
        for player in current_team[:5]:  # Bottom 5 by score
            issues = []
            
            if player['availability'] != 'a':
                issues.append(f"**INJURED/UNAVAILABLE** - {player['news']}")
            
            if player['chance_of_playing'] and player['chance_of_playing'] < 75:
                issues.append(f"Doubt for next match ({player['chance_of_playing']}% chance)")
            
            if player['form'] < 3.0:
                issues.append(f"Poor form ({player['form']})")
            
            if player['avg_fixture_difficulty'] > 3.5:
                issues.append(f"Difficult fixtures (avg difficulty: {player['avg_fixture_difficulty']:.1f})")
            
            if player['expected_points_next'] < 2.0:
                issues.append(f"Low expected points ({player['expected_points_next']:.1f})")
            
            if issues:
                problem_players.append((player, issues))
        
        for player, issues in problem_players:
            report.append(f"### {player['name']} ({player['position']}) - {player['team']} - £{player['price']:.1f}m")
            for issue in issues:
                report.append(f"- {issue}")
            
            # Show upcoming fixtures
            fixtures_str = ", ".join([
                f"{f['opponent']}({'H' if f['home'] else 'A'}, FDR:{f['difficulty']})"
                for f in player['upcoming_fixtures'][:3]
            ])
            report.append(f"- Next 3 fixtures: {fixtures_str}")
            report.append("")
            
            # Find replacement suggestions
            available_budget = player['price'] + (self.team_data['last_deadline_bank'] / 10.0)
            targets = self.find_transfer_targets(position=player['position'], max_price=available_budget)
            
            report.append(f"**Suggested replacements (max £{available_budget:.1f}m):**")
            for i, target in enumerate(targets[:3], 1):
                fixtures_str = ", ".join([
                    f"{f['opponent']}({'H' if f['home'] else 'A'}, FDR:{f['difficulty']})"
                    for f in target['upcoming_fixtures'][:3]
                ])
                report.append(f"{i}. **{target['name']}** ({target['team']}) - £{target['price']:.1f}m")
                report.append(f"   - Form: {target['form']}, PPG: {target['points_per_game']}, xP: {target['expected_points_next']:.1f}")
                report.append(f"   - Fixtures: {fixtures_str}")
                report.append(f"   - Selected by: {target['selected_by']:.1f}%")
            
            report.append("")
            report.append("---")
            report.append("")
        
        if not problem_players:
            report.append("✅ No immediate concerns with your team!")
            report.append("")
        
        # Top performers
        report.append("## 🌟 YOUR TOP PERFORMERS")
        report.append("")
        top_players = sorted(current_team, key=lambda x: x['score'], reverse=True)[:5]
        for player in top_players:
            fixtures_str = ", ".join([
                f"{f['opponent']}({'H' if f['home'] else 'A'}, FDR:{f['difficulty']})"
                for f in player['upcoming_fixtures'][:3]
            ])
            report.append(f"- **{player['name']}** ({player['position']}) - {player['team']} - £{player['price']:.1f}m")
            report.append(f"  Form: {player['form']}, Expected: {player['expected_points_next']:.1f}, Fixtures: {fixtures_str}")
        
        report.append("")
        
        # Captain recommendations
        report.append("## 👑 CAPTAIN RECOMMENDATIONS")
        report.append("")
        captain_candidates = sorted(current_team, key=lambda x: x['expected_points_next'], reverse=True)[:3]
        for i, player in enumerate(captain_candidates, 1):
            report.append(f"{i}. **{player['name']}** - Expected: {player['expected_points_next']:.1f} points")
            report.append(f"   Next fixture: {player['upcoming_fixtures'][0]['opponent'] if player['upcoming_fixtures'] else 'N/A'}")
        
        return "\n".join(report)


def main():
    import os
    
    # Get team ID from environment variable or use default
    team_id = os.environ.get('FPL_TEAM_ID')
    
    if not team_id:
        print("Error: FPL_TEAM_ID environment variable not set")
        print("Please set it in your GitHub repository secrets")
        return
    
    try:
        analyzer = FPLAnalyzer(team_id)
        report = analyzer.generate_recommendations()
        
        # Save report
        with open('fpl_report.md', 'w') as f:
            f.write(report)
        
        print("Report generated successfully!")
        print("\n" + "="*50)
        print(report)
        
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
