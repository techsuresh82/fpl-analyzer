# FPL Weekly Analyzer 🏆⚽

Automated Fantasy Premier League team analysis that runs weekly on GitHub Actions and provides transfer recommendations based on comprehensive data analysis.

## Features

✅ **Comprehensive Analysis**
- Player form analysis
- Fixture difficulty ratings (next 5 games)
- Expected points predictions
- Price change tracking
- Injury and availability monitoring
- Points per game statistics
- Ownership percentages

✅ **Smart Recommendations**
- Identifies players to transfer out
- Suggests replacements within your budget
- Recommends captain choices
- Highlights top performers
- Considers multiple factors weighted intelligently

✅ **Automated Weekly Reports**
- Runs automatically every Friday at 9 AM UTC
- Creates a GitHub Issue with full analysis
- Commits report to repository
- Can be triggered manually anytime

## Setup Instructions

### 1. Fork or Create Repository

1. Create a new GitHub repository (public or private)
2. Upload these files to your repository:
   - `fpl_analyzer.py`
   - `.github/workflows/weekly_analysis.yml`
   - `requirements.txt`
   - `README.md`

### 2. Find Your FPL Team ID

Your team ID is in the URL when you view your team on the FPL website:

```
https://fantasy.premierleague.com/entry/YOUR_TEAM_ID/event/1
                                          ^^^^^^^^^^^^
```

For example, if the URL is `.../entry/123456/event/1`, your team ID is `123456`.

### 3. Add Team ID as Secret

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `FPL_TEAM_ID`
5. Value: Your team ID (just the number)
6. Click **Add secret**

### 4. Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. If prompted, click **"I understand my workflows, go ahead and enable them"**
3. You should see the "FPL Weekly Analysis" workflow

### 5. Enable Issue Creation (Important!)

1. Go to **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Select **"Read and write permissions"**
4. Check ✅ **"Allow GitHub Actions to create and approve pull requests"**
5. Click **Save**

## Usage

### Automatic Weekly Analysis

The analysis runs automatically every **Friday at 9:00 AM UTC**. You'll receive a notification when a new issue is created.

To change the schedule, edit `.github/workflows/weekly_analysis.yml`:

```yaml
schedule:
  - cron: '0 9 * * 5'  # minute hour day-of-month month day-of-week
```

Examples:
- `'0 9 * * 5'` - Every Friday at 9 AM
- `'0 18 * * 4'` - Every Thursday at 6 PM
- `'0 12 * * 2,5'` - Tuesday and Friday at noon

### Manual Trigger

To run analysis immediately:

1. Go to **Actions** tab
2. Click **FPL Weekly Analysis**
3. Click **Run workflow** → **Run workflow**

### View Reports

Reports are available in two places:

1. **GitHub Issues** - Each week creates a new issue with the full report
2. **Repository** - The `fpl_report.md` file is updated with the latest analysis

## Report Structure

Each report includes:

### 1. Team Status
- Team value
- Money in the bank
- Available free transfers

### 2. Players to Transfer Out ⚠️
- Problem players identified with reasons:
  - Injuries/unavailability
  - Poor form
  - Difficult fixtures
  - Low expected points
- Suggested replacements for each player
- Budget-aware recommendations

### 3. Top Performers 🌟
- Your best 5 players
- Form and fixture analysis

### 4. Captain Recommendations 👑
- Top 3 captain choices
- Based on expected points

## How the Analysis Works

### Scoring Algorithm

Each player receives a score based on:

```python
Score = (Form × 2.0) + (Points per Game × 1.5) + (Expected Points × 1.0) + ((5 - Fixture Difficulty) × 0.5)
```

**Penalties:**
- Injured/unavailable: Score × 0.5
- Doubtful (<75% chance): Score × 0.7

### Criteria Breakdown

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Form** | 2.0 | Recent performance trend |
| **Points per Game** | 1.5 | Season average |
| **Expected Points** | 1.0 | Next gameweek prediction |
| **Fixtures** | 0.5 | Next 5 games difficulty |
| **Availability** | Penalty | Injuries/suspensions |

## Customization

### Change Analysis Criteria

Edit `fpl_analyzer.py` and modify the scoring formula in the `analyze_player` method:

```python
score = (
    form * 2.0 +                    # Adjust weight
    points_per_game * 1.5 +         # Adjust weight
    expected_points * 1.0 +         # Adjust weight
    (5 - avg_difficulty) * 0.5      # Adjust weight
)
```

### Change Number of Transfer Targets

Modify this line to show more/fewer alternatives:

```python
targets = self.find_transfer_targets(position=player['position'], max_price=available_budget)[:3]  # Change 3 to any number
```

### Change Number of Fixtures Analyzed

Modify the default in `calculate_fixture_difficulty`:

```python
def calculate_fixture_difficulty(self, player_id, num_fixtures=5):  # Change 5 to analyze more/fewer fixtures
```

## Troubleshooting

### "FPL_TEAM_ID environment variable not set"
- Make sure you added your team ID as a repository secret
- Check the secret name is exactly `FPL_TEAM_ID`

### Workflow doesn't run
- Ensure GitHub Actions are enabled in your repository
- Check that workflow permissions are set to "Read and write"
- For private repos, ensure you have GitHub Actions minutes available

### No issues are created
- Verify workflow permissions include "Allow GitHub Actions to create and approve pull requests"
- Check the Actions tab for error messages

### API Rate Limiting
- The FPL API is generally permissive
- If you hit rate limits, add a delay or reduce frequency

## Data Source

All data comes from the official Fantasy Premier League API:
- `https://fantasy.premierleague.com/api/bootstrap-static/` - Player and team data
- `https://fantasy.premierleague.com/api/entry/{team_id}/` - Your team data
- `https://fantasy.premierleague.com/api/fixtures/` - Fixture data

## Running Locally

To test the script locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Set your team ID
export FPL_TEAM_ID=your_team_id

# Run the analyzer
python fpl_analyzer.py
```

The report will be saved to `fpl_report.md`.

## Contributing

Feel free to customize the analysis criteria, add new features, or improve the recommendations algorithm!

## License

This project uses publicly available FPL API data. Use responsibly and in accordance with Fantasy Premier League's terms of service.

## Disclaimer

This tool provides recommendations based on statistical analysis. Always make your own informed decisions for your FPL team! 🎯

---

**Good luck with your FPL season!** 🏆
