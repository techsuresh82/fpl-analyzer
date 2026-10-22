#!/usr/bin/env python3
"""
FPL Team Analyzer - Weekly Transfer Recommendations
Analyzes FPL teams based on form, fixtures, expected points, price trends, and injuries.
Supports multiple teams and generates markdown + HTML reports for GitHub issues and artifacts.
"""

import html
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
    def money(value):
        return f"£{float(value):.1f}m"

    @staticmethod
    def signed(value):
        return f"{value:+.1f}"

    @staticmethod
    def mini_bar(value, max_value=10, width=10, fill='█', empty='░'):
        if max_value <= 0:
            max_value = 1
        ratio = max(0, min(1, float(value) / max_value))
        filled = int(ratio * width)
        return f"{fill * filled}{empty * (width - filled)}"

    def get_free_transfers_available(self):
        """Return how many free transfers are available and transfer cost already used."""
        history = self.team_picks.get('entry_history', {}) if self.team_picks else {}
        transfers_used = int(history.get('event_transfers', 0) or 0)
        transfer_cost = int(history.get('event_transfers_cost', 0) or 0)
        free_transfers = max(0, 1 - transfers_used)
        if free_transfers == 0 and transfer_cost == 0 and transfers_used == 0:
            free_transfers = 1
        return free_transfers, transfers_used, transfer_cost

    def format_fixtures(self, fixtures, limit=3):
        if not fixtures:
            return "N/A"
        pieces = []
        for fixture in fixtures[:limit]:
            pieces.append(f"{fixture['opponent']}({'H' if fixture['home'] else 'A'}, FDR:{fixture['difficulty']})")
        return ", ".join(pieces)

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
            'score': score,
            'xp_per_m': (expected_points / price) if price > 0 else 0,
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

    def build_transfer_recommendation(self, player, free_transfers):
        """Create one transfer suggestion for a problem player, considering free transfers and value."""
        budget = player['price'] + (self.team_data.get('last_deadline_bank', 0) / 10.0)
        targets = self.find_transfer_targets(position=player['position'], max_price=budget)
        if not targets:
            return None

        ranked = []
        for target in targets[:10]:
            net_cost = target['price'] - player['price']
            if free_transfers > 0:
                transfer_cost = 0.0
                cost_penalty = 0.0
            else:
                transfer_cost = max(0.0, net_cost)
                cost_penalty = transfer_cost * 0.8

            value_score = (target['expected_points_next'] / target['price']) if target['price'] > 0 else 0
            total_score = target['score'] + (value_score * 10) - cost_penalty
            ranked.append({
                'target': target,
                'net_cost': net_cost,
                'transfer_cost': transfer_cost,
                'value_score': value_score,
                'total_score': total_score,
            })

        ranked.sort(key=lambda x: x['total_score'], reverse=True)
        return ranked[0] if ranked else None

    def generate_markdown_report(self):
        """Generate the markdown issue body."""
        self.fetch_bootstrap_data()
        self.fetch_team_data()
        self.fetch_fixtures()

        current_team = self.get_current_team()
        current_team.sort(key=lambda x: x['score'])
        free_transfers, transfers_used, transfer_cost = self.get_free_transfers_available()

        risk_counts = {'Low': 0, 'Medium': 0, 'High': 0}
        captain_candidates = sorted(current_team, key=lambda x: x['expected_points_next'], reverse=True)[:3]

        for player in current_team:
            if player['availability'] != 'a' or (player['chance_of_playing'] and player['chance_of_playing'] < 75):
                risk = 'High'
            elif player['avg_fixture_difficulty'] > 3.5 or player['form'] < 3.0:
                risk = 'Medium'
            else:
                risk = 'Low'
            risk_counts[risk] += 1

        lines = []
        lines.append(f"# FPL WEEKLY ANALYSIS REPORT - {self.team_data['name']}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Manager: {self.team_data['player_first_name']} {self.team_data['player_last_name']}")
        lines.append(f"Team: {self.team_data['name']}")
        lines.append(f"Team ID: {self.team_id}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Team | Value | Bank | Free transfers | Transfers used | Captain pick |")
        lines.append("|------|-------|------|----------------|----------------|--------------|")
        lines.append(
            f"| {self.team_data['name']} | {self.money(self.team_data.get('last_deadline_value', 0) / 10.0)} | "
            f"{self.money(self.team_data.get('last_deadline_bank', 0) / 10.0)} | {free_transfers} | {transfers_used} | "
            f"{captain_candidates[0]['name'] if captain_candidates else 'N/A'} |"
        )
        lines.append("")

        lines.append("## Risk Snapshot")
        lines.append("")
        lines.append("```mermaid")
        lines.append("pie title Team Risk Distribution")
        lines.append(f"    \"Low\" : {risk_counts['Low']}")
        lines.append(f"    \"Medium\" : {risk_counts['Medium']}")
        lines.append(f"    \"High\" : {risk_counts['High']}")
        lines.append("```")
        lines.append("")

        lines.append("## Captaincy Comparison")
        lines.append("")
        lines.append("```mermaid")
        lines.append("xychart-beta")
        lines.append("    title Expected Points Next GW")
        captain_names = ", ".join(p['name'] for p in captain_candidates)
        captain_xp = ", ".join(f"{p['expected_points_next']:.1f}" for p in captain_candidates)
        lines.append(f"    x-axis [{captain_names}]")
        lines.append("    y-axis \"Expected xP\" 0 --> 12")
        lines.append(f"    bar [{captain_xp}]")
        lines.append("```")
        lines.append("")

        lines.append("## Risk Table")
        lines.append("")
        lines.append("| Player | Pos | Form | xP | FDR | Risk | Cost |")
        lines.append("|--------|-----|------|----|-----|------|------|")
        for player in current_team[:8]:
            if player['availability'] != 'a' or (player['chance_of_playing'] and player['chance_of_playing'] < 75):
                risk = 'High'
            elif player['avg_fixture_difficulty'] > 3.5 or player['form'] < 3.0:
                risk = 'Medium'
            else:
                risk = 'Low'
            lines.append(
                f"| {player['name']} | {player['position']} | {player['form']:.1f} {self.mini_bar(player['form'], max_value=10, width=8)} | "
                f"{player['expected_points_next']:.1f} | {player['avg_fixture_difficulty']:.1f} | {risk} | {self.money(player['price'])} |"
            )
        lines.append("")

        lines.append("## ⚠️ Players to Consider Transferring Out")
        lines.append("")
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
            lines.append("✅ No immediate concerns with your team!")
            lines.append("")
        else:
            for player, issues in problem_players:
                transfer_pick = self.build_transfer_recommendation(player, free_transfers)
                target = transfer_pick['target'] if transfer_pick else None
                net_cost = transfer_pick['net_cost'] if transfer_pick else 0
                transfer_cost = transfer_pick['transfer_cost'] if transfer_pick else 0
                value_score = transfer_pick['value_score'] if transfer_pick else 0

                lines.append(f"### {player['name']} ({player['position']}) - {player['team']} - {self.money(player['price'])}")
                for issue in issues:
                    lines.append(f"- {issue}")
                lines.append(f"- Next 3 fixtures: {self.format_fixtures(player['upcoming_fixtures'])}")
                lines.append(f"- Free transfers available: {free_transfers}")
                if target:
                    lines.append(f"- Suggested move: {player['name']} OUT -> {target['name']} IN")
                    lines.append(f"- Net cost: {self.money(net_cost)}")
                    lines.append(f"- Transfer hit if no free transfer: {self.money(transfer_cost)}")
                    lines.append(f"- Value score: {value_score:.2f} xP per £m")
                    lines.append(f"- Target reason: form {target['form']:.1f}, xP {target['expected_points_next']:.1f}, fixtures {self.format_fixtures(target['upcoming_fixtures'])}")
                    lines.append("")
                    lines.append("| Out | In | Net cost | xP/£m | Notes |")
                    lines.append("|-----|----|----------|-------|-------|")
                    lines.append(
                        f"| {player['name']} | {target['name']} | {self.money(net_cost)} | {value_score:.2f} | "
                        f"{'Free transfer available' if free_transfers > 0 else 'Transfer hit applies'} |"
                    )
                else:
                    lines.append("- Suggested move: no suitable replacement in budget")
                lines.append("")
                lines.append("---")
                lines.append("")

        lines.append("## 🌟 Top Performers")
        lines.append("")
        lines.append("| Player | Pos | Team | Form | xP | Fixtures |")
        lines.append("|--------|-----|------|------|----|----------|")
        for player in sorted(current_team, key=lambda x: x['score'], reverse=True)[:5]:
            lines.append(
                f"| {player['name']} | {player['position']} | {player['team']} | {player['form']:.1f} | "
                f"{player['expected_points_next']:.1f} | {self.format_fixtures(player['upcoming_fixtures'])} |"
            )
        lines.append("")

        lines.append("## 👑 Captain Recommendations")
        lines.append("")
        for i, player in enumerate(captain_candidates, 1):
            next_fixture = player['upcoming_fixtures'][0]['opponent'] if player['upcoming_fixtures'] else 'N/A'
            lines.append(f"{i}. **{player['name']}** - Expected: {player['expected_points_next']:.1f} points | Next fixture: {next_fixture}")
        lines.append("")

        if free_transfers > 0:
            lines.append("## Transfer Strategy")
            lines.append("")
            lines.append(f"- You have {free_transfers} free transfer(s) available this GW.")
            lines.append("- Prioritize moves that improve xP without a transfer hit or with a small net cost.")
            lines.append("- If a player has poor fixtures or poor form, the best move is often a cheaper, higher-xP alternative in the same position.")
        else:
            lines.append("## Transfer Strategy")
            lines.append("")
            lines.append("- No free transfers available this GW.")
            lines.append("- Favor low-net-cost moves and only do transfers that materially improve xP or fixture difficulty.")
            lines.append("- If the net cost is high, make sure the incoming player has stronger expected points and fixtures than the outgoing player.")

        return "\n".join(lines)

    def generate_html_report(self, markdown_text):
        """Create a simple styled HTML artifact from the markdown text."""
        escaped = html.escape(markdown_text)
        html_body = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>FPL Weekly Report</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 32px; }
    .container { max-width: 1100px; margin: 0 auto; }
    .box { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; }
    h1, h2, h3 { color: #f0f6fc; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0 24px; }
    th, td { border: 1px solid #30363d; padding: 10px 12px; text-align: left; }
    th { background: #21262d; }
    code, pre { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; overflow: auto; }
    a { color: #58a6ff; }
  </style>
</head>
<body>
  <div class="container">
    <div class="box">
      <pre>{content}</pre>
    </div>
  </div>
</body>
</html>
        """.replace('{content}', escaped)
        return html_body


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
        report = analyzer.generate_markdown_report()

        team_name = analyzer.team_data.get('name', f'Team {team_id}') if analyzer.team_data else f'Team {team_id}'
        value = (analyzer.team_data.get('last_deadline_value', 0) / 10.0) if analyzer.team_data else 0
        bank = (analyzer.team_data.get('last_deadline_bank', 0) / 10.0) if analyzer.team_data else 0
        free_transfers, transfers_used, _ = analyzer.get_free_transfers_available()
        captain = sorted(analyzer.get_current_team(), key=lambda x: x['expected_points_next'], reverse=True)[:1]
        captain_name = captain[0]['name'] if captain else 'N/A'

        summary_rows.append(f"| {team_name} | {team_id} | {value:.1f}m | {bank:.1f}m | {free_transfers} | {transfers_used} | {captain_name} |")
        sections.append(report)

    summary = [
        "# FPL WEEKLY ANALYSIS REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Team Overview",
        "| Team | Team ID | Value | Bank | Free transfers | Transfers used | Captain pick |",
        "|------|---------|-------|------|----------------|----------------|--------------|",
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
            markdown_report = analyzer.generate_markdown_report()
            html_report = analyzer.generate_html_report(markdown_report)
        else:
            markdown_report = build_combined_report(team_ids)
            html_report = "<html><body><pre>" + html.escape(markdown_report) + "</pre></body></html>"

        with open('fpl_report.md', 'w', encoding='utf-8') as f:
            f.write(markdown_report)

        with open('fpl_report.html', 'w', encoding='utf-8') as f:
            f.write(html_report)

        print("Report generated successfully!")
        print("\n" + "=" * 50)
        print(markdown_report)

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
