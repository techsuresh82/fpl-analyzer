#!/usr/bin/env python3
"""
FPL Team Analyzer - Weekly Transfer Recommendations
Analyzes FPL teams based on form, fixtures, expected points, price trends, and injuries.
Supports multiple teams in one report and produces markdown tables/charts for easier reading.
"""

import os
from datetime import datetime

import requests


class FPLAnalyzer:
    def __init__(self, team_id):
        self.team_id = str(team_id).strip()
        self.base_url = "https://fantasy.premierleague.com/api"
        self.bootstrap_data = None
        self.team_data = None
        self.fixtures_data = None
        self.team_picks = None

    def fetch_bootstrap_data(self):
        """Fetch general FPL data including all players."""
        response = requests.get(f"{self.base_url}/bootstrap-static/")
        response.raise_for_status()
        self.bootstrap_data = response.json()

    def fetch_team_data(self):
        """Fetch user's team data and picks for the current gameweek."""
        response = requests.get(f"{self.base_url}/entry/{self.team_id}/")
        response.raise_for_status()
        self.team_data = response.json()

        current_gw = None
        for event in self.bootstrap_data['events']:
            if event.get('is_current'):
                current_gw = event['id']
                break
            if event.get('is_next'):
                current_gw = event['id']
                break

        if current_gw is None:
            for event in reversed(self.bootstrap_data['events']):
                if event.get('finished'):
                    current_gw = event['id'] + 1
                    break

        if current_gw is None:
            current_gw = 1

        print(f"Fetching team data for Gameweek {current_gw}")
        picks_response = requests.get(f"{self.base_url}/entry/{self.team_id}/event/{current_gw}/picks/")
        picks_response.raise_for_status()
        self.team_picks = picks_response.json()

    def fetch_fixtures(self):
        """Fetch upcoming fixtures."""
        response = requests.get(f"{self.base_url}/fixtures/")
        response.raise_for_status()
        self.fixtures_data = response.json()

    def get_player_by_id(self, player_id):
        """Get player details from bootstrap data."""
        for player in self.bootstrap_data['elements']:
            if player['id'] == player_id:
                return player
        return None

    def get_team_name(self, team_id):
        """Get team name from ID."""
        for team in self.bootstrap_data['teams']:
            if team['id'] == team_id:
                return team['name']
        return "Unknown"

    def get_position_name(self, element_type):
        """Convert element type to position name."""
        positions = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        return positions.get(element_type, 'Unknown')

    def calculate_fixture_difficulty(self, player_id, num_fixtures=5):
        """Calculate upcoming fixture difficulty for a player."""
        player = self.get_player_by_id(player_id)
        if not player:
            return 0, []

        team_id = player['team']
        upcoming_fixtures = []

        for fixture in self.fixtures_data:
            if not fixture.get('finished') and fixture.get('event') is not None:
                if fixture.get('team_h') == team_id:
                    upcoming_fixtures.append({
                        'opponent': self.get_team_name(fixture.get('team_a')),
                        'difficulty': fixture.get('team_h_difficulty', 0),
                        'home': True,
                        'event': fixture.get('event')
                    })
                elif fixture.get('team_a') == team_id:
                    upcoming_fixtures.append({
                        'opponent': self.get_team_name(fixture.get('team_h')),
                        'difficulty': fixture.get('team_a_difficulty', 0),
                        'home': False,
                        'event': fixture.get('event')
                    })

        upcoming_fixtures.sort(key=lambda x: x['event'] if x['event'] is not None else 999)
        upcoming_fixtures = upcoming_fixtures[:num_fixtures]

        avg_difficulty = sum(f['difficulty'] for f in upcoming_fixtures) / len(upcoming_fixtures) if upcoming_fixtures else 0
        return avg_difficulty, upcoming_fixtures

    @staticmethod
    def format_money(value):
        return f"£{float(value):.1f}m"

    @staticmethod
    def format_minus_plus(number):
        return f"{number:+.1f}"

    @staticmethod
    def bar_chart(value, max_value=10, width=10, empty_char='░', fill_char='█'):
        if max_value <= 0:
            max_value = 1
        normalized = max(0, min(1, float(value) / max_value))
        filled = int(round(normalized * width))
        return f"{fill_char * filled}{empty_char * (width - filled)}"

    def format_fixtures(self, fixtures, limit=3):
        """Format upcoming fixtures for markdown output."""
        if not fixtures:
            return "N/A"

        parts = []
        for fixture in fixtures[:limit]:
            parts.append(f"{fixture['opponent']}({'H' if fixture['home'] else 'A'}, FDR:{fixture['difficulty']})")
        return ", ".join(parts)

    def analyze_player(self, player_id):
        """Comprehensive player analysis."""
        player = self.get_player_by_id(player_id)
        if not player:
            return None

        form = float(player.get('form') or 0)
        points_per_game = float(player.get('points_per_game') or 0)
        expected_points = float(player.get('ep_next') or 0)
        price = (player.get('now_cost') or 0) / 10.0
        price_change = (player.get('cost_change_start') or 0) / 10.0
        selected_by = float(player.get('selected_by_percent') or 0)

        availability = player.get('status', 'a')
        news = player.get('news', '')
        chance_of_playing = player.get('chance_of_playing_next_round')
        avg_difficulty, fixtures = self.calculate_fixture_difficulty(player_id)

        score = (
            form * 2.0 +
            points_per_game * 1.5 +
            expected_points * 1.0 +
            (5 - avg_difficulty) * 0.5
        )

        if availability != 'a':
            score *= 0.5
        if chance_of_playing and chance_of_playing < 75:
            score *= 0.7

        return {
            'id': player_id,
            'name': player.get('web_name', 'Unknown'),
            'full_name': f"{player.get('first_name', '')} {player.get('second_name', '')}".strip(),
            'team': self.get_team_name(player.get('team')),
            'position': self.get_position_name(player.get('element_type')),
            'price': price,
            'price_change': price_change,
            'form': form,
            'points_per_game': points_per_game,
            'expected_points_next': expected_points,
            'total_points': player.get('total_points', 0),
            'selected_by': selected_by,
            'availability': availability,
            'news': news,
            'chance_of_playing': chance_of_playing,
            'avg_fixture_difficulty': avg_difficulty,
            'upcoming_fixtures': fixtures,
            'score': score
        }

    def get_current_team(self):
        """Get current team with analysis."""
        current_team = []
        for pick in self.team_picks.get('picks', []):
            analysis = self.analyze_player(pick['element'])
            if analysis:
                analysis['is_captain'] = pick.get('is_captain', False)
                analysis['is_vice_captain'] = pick.get('is_vice_captain', False)
                analysis['multiplier'] = pick.get('multiplier', 0)
                current_team.append(analysis)
        return current_team

    def find_transfer_targets(self, position=None, max_price=None):
        """Find potential transfer targets."""
        candidates = []

        for player in self.bootstrap_data['elements']:
            if position and self.get_position_name(player.get('element_type')) != position:
                continue

            if max_price and (player.get('now_cost') or 0) / 10.0 > max_price:
                continue

            if player.get('status') != 'a':
                continue

            analysis = self.analyze_player(player['id'])
            if analysis:
                candidates.append(analysis)

        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:20]

    def generate_recommendations(self):
        """Generate transfer recommendations for one team."""
        print("Fetching FPL data...")
        self.fetch_bootstrap_data()
        self.fetch_team_data()
        self.fetch_fixtures()

        print(f"Analyzing team: {self.team_data['name']}")
        print(f"Manager: {self.team_data['player_first_name']} {self.team_data['player_last_name']}")
        print(f"Team ID: {self.team_id}")

        current_team = self.get_current_team()
        current_team.sort(key=lambda x: x['score'])

        report = []
        report.append(f"# FPL WEEKLY ANALYSIS REPORT - {self.team_data['name']}")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Manager: {self.team_data['player_first_name']} {self.team_data['player_last_name']}")
        report.append(f"Team: {self.team_data['name']}")
        report.append(f"Team ID: {self.team_id}")
        report.append("")

        report.append("## Team Status")
        report.append(f"- Team Value: {self.format_money(self.team_data.get('last_deadline_value', 0) / 10.0)}")
        report.append(f"- In Bank: {self.format_money(self.team_data.get('last_deadline_bank', 0) / 10.0)}")
        entry_history = self.team_picks.get('entry_history', {}) if self.team_picks else {}
        report.append(f"- Transfers used this GW: {entry_history.get('event_transfers', 0)}")
        report.append(f"- Transfer cost: {entry_history.get('event_transfers_cost', 0)}")
        report.append("")

        report.append("## Risk Snapshot")
        report.append("")
        report.append("| Player | Pos | Form | xP | FDR | Risk | Trend |")
        report.append("|--------|-----|------|----|-----|------|-------|")

        for player in current_team[:8]:
            risk = "Low"
            if player['availability'] != 'a' or (player['chance_of_playing'] and player['chance_of_playing'] < 75):
                risk = "High"
            elif player['avg_fixture_difficulty'] > 3.5 or player['form'] < 3.0:
                risk = "Medium"

            form_bar = self.bar_chart(player['form'], max_value=10, width=10)
            report.append(
                f"| {player['name']} | {player['position']} | {player['form']:.1f} {form_bar} | "
                f"{player['expected_points_next']:.1f} | {player['avg_fixture_difficulty']:.1f} | {risk} | "
                f"{self.format_minus_plus(player['price_change'])} |"
            )

        report.append("")

        report.append("## ⚠️ Players to Consider Transferring Out")
        report.append("")

        problem_players = []
        for player in current_team[:5]:
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

        if not problem_players:
            report.append("✅ No immediate concerns with your team!")
            report.append("")
        else:
            for player, issues in problem_players:
                report.append(f"### {player['name']} ({player['position']}) - {player['team']} - £{player['price']:.1f}m")
                for issue in issues:
                    report.append(f"- {issue}")

                report.append(f"- Next 3 fixtures: {self.format_fixtures(player['upcoming_fixtures'])}")
                report.append("")

                available_budget = player['price'] + (self.team_data.get('last_deadline_bank', 0) / 10.0)
                targets = self.find_transfer_targets(position=player['position'], max_price=available_budget)

                report.append(f"**Suggested replacements (max {self.format_money(available_budget)}):**")
                report.append("| Replacement | Team | Price | Form | xP | Fixtures |")
                report.append("|-------------|------|-------|------|----|----------|")

                for target in targets[:3]:
                    report.append(
                        f"| {target['name']} | {target['team']} | {self.format_money(target['price'])} | "
                        f"{target['form']:.1f} | {target['expected_points_next']:.1f} | {self.format_fixtures(target['upcoming_fixtures'])} |"
                    )

                report.append("")
                report.append("---")
                report.append("")

        report.append("## 🌟 Your Top Performers")
        report.append("")
        report.append("| Player | Pos | Team | Form | xP | Fixtures |")
        report.append("|--------|-----|------|------|----|----------|")
        top_players = sorted(current_team, key=lambda x: x['score'], reverse=True)[:5]
        for player in top_players:
            report.append(
                f"| {player['name']} | {player['position']} | {player['team']} | {player['form']:.1f} | "
                f"{player['expected_points_next']:.1f} | {self.format_fixtures(player['upcoming_fixtures'])} |"
            )

        report.append("")

        report.append("## 👑 Captain Recommendations")
        report.append("")
        captain_candidates = sorted(current_team, key=lambda x: x['expected_points_next'], reverse=True)[:3]
        for i, player in enumerate(captain_candidates, 1):
            fixture_label = player['upcoming_fixtures'][0]['opponent'] if player['upcoming_fixtures'] else 'N/A'
            report.append(f"{i}. **{player['name']}** - Expected: {player['expected_points_next']:.1f} points | Next fixture: {fixture_label}")

        return "\n".join(report)


def get_team_ids_from_env():
    """Support both a single legacy FPL_TEAM_ID and a comma-separated FPL_TEAM_IDS list."""
    team_ids = []

    multi = os.environ.get('FPL_TEAM_IDS', '').strip()
    if multi:
        team_ids.extend([team_id.strip() for team_id in multi.split(',') if team_id.strip()])

    legacy = os.environ.get('FPL_TEAM_ID', '').strip()
    if legacy and legacy not in team_ids:
        team_ids.append(legacy)

    return team_ids


def build_combined_report(team_ids):
    """Build a single report across multiple teams."""
    summary_rows = []
    sections = []

    for team_id in team_ids:
        analyzer = FPLAnalyzer(team_id)
        analyzer.fetch_bootstrap_data()
        analyzer.fetch_team_data()
        analyzer.fetch_fixtures()
        report = analyzer.generate_recommendations()

        team_name = analyzer.team_data.get('name', f'Team {team_id}') if analyzer.team_data else f'Team {team_id}'
        value = (analyzer.team_data.get('last_deadline_value', 0) / 10.0) if analyzer.team_data else 0
        bank = (analyzer.team_data.get('last_deadline_bank', 0) / 10.0) if analyzer.team_data else 0
        transfers_used = analyzer.team_picks.get('entry_history', {}).get('event_transfers', 0) if analyzer.team_picks else 0

        summary_rows.append(f"| {team_name} | {team_id} | {value:.1f}m | {bank:.1f}m | {transfers_used} |")
        sections.append(report)

    summary = [
        "# FPL WEEKLY ANALYSIS REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Team Overview",
        "| Team | Team ID | Value | Bank | Transfers used |",
        "|------|---------|-------|------|----------------|",
    ]
    summary.extend(summary_rows)
    summary.extend(["", "---", ""])
    return "\n".join(summary + sections)


def main():
    team_ids = get_team_ids_from_env()

    if not team_ids:
        print("Error: FPL_TEAM_ID or FPL_TEAM_IDS environment variable not set")
        print("Please set it in your GitHub repository secrets")
        return

    try:
        if len(team_ids) == 1:
            analyzer = FPLAnalyzer(team_ids[0])
            report = analyzer.generate_recommendations()
        else:
            report = build_combined_report(team_ids)

        with open('fpl_report.md', 'w') as f:
            f.write(report)

        print("Report generated successfully!")
        print("\n" + "=" * 50)
        print(report)

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
