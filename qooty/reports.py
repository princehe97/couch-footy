"""File I/O: commentary text, interchange logs, stat CSVs, and scoring summaries.

Every function takes a MatchState so there is zero global state.
All file handles use ``with`` to guarantee they are closed.
"""

from __future__ import annotations

import csv
from pathlib import Path

from qooty.constants import H2H_EXTRA_FIELDS, STAT_CATEGORIES, Possession
from qooty.match_state import MatchState
from qooty.paths import get_output_path


BASIC_PLAYER_STATS = ("HO", "K", "M", "HB", "T", "FF", "FA", "G", "B", "D", "DT")
ADVANCED_PLAYER_STATS = tuple(cat for cat in STAT_CATEGORIES if cat not in BASIC_PLAYER_STATS)


def write_player_stat_exports(ms: MatchState, output_dir: Path | None = None) -> None:
    """Export rectangular basic/advanced tables for the latest match.

    Keep each team's roster separate so matching player names cannot overwrite
    each other. Values, including the standard DT score, come from state.
    """
    for filename, categories in (
        ("BasicPlayerStats.csv", BASIC_PLAYER_STATS),
        ("AdvancedPlayerStats.csv", ADVANCED_PLAYER_STATS),
    ):
        path = output_dir / filename if output_dir is not None else Path(get_output_path(filename))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["PLAYER", "TEAM", *categories])
            writer.writeheader()
            for team in (ms.home, ms.away):
                for player in team.players:
                    stats = team.stats[player]
                    writer.writerow({
                        "PLAYER": player,
                        "TEAM": team.name,
                        **{category: stats[category] for category in categories},
                    })

try:
    import pandas as pd  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    pd = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Commentary text file
# ---------------------------------------------------------------------------

def write_match_start_commentary(ms: MatchState) -> None:
    """Overwrite Commentary.txt with the match header and team line-ups."""
    h, a = ms.home, ms.away
    header = f"MATCH COMMENCING SHORTLY ... {h.name} vs {a.name}\n\n"

    # Build lineup string (code-block style, mirrors original)
    lines = [
        f"[code=rich]                       {a.name}",
        f"FB: {a.player_at('rBP')}|{a.player_at('FB')}|{a.player_at('lBP')}",
        f"FF: {h.player_at('lFP')}|{h.player_at('FF')}|{h.player_at('rFP')}",
        f"HB: {a.player_at('rHBF')}|{a.player_at('CHB')}|{a.player_at('lHBF')}",
        f"HF: {h.player_at('lHFF')}|{h.player_at('CHF')}|{h.player_at('rHFF')}",
        f"C: {a.player_at('rW')}|{a.player_at('C')}|{a.player_at('lW')}",
        f"C: {h.player_at('lW')}|{h.player_at('C')}|{h.player_at('rW')}",
        f"HF: {a.player_at('rHFF')}|{a.player_at('CHF')}|{a.player_at('lHFF')}",
        f"HB: {h.player_at('lHBF')}|{h.player_at('CHB')}|{h.player_at('rHBF')}",
        f"FF: {a.player_at('rFP')}|{a.player_at('FF')}|{a.player_at('lFP')}",
        f"FB: {h.player_at('lBP')}|{h.player_at('FB')}|{h.player_at('rBP')}",
        f"                       {h.name}",
        "",
        "[/code]"
        f"{h.name} FOLL: {h.player_at('RUCK')}|{h.player_at('RR')}|{h.player_at('R')}",
        f"{a.name} FOLL: {a.player_at('RUCK')}|{a.player_at('RR')}|{a.player_at('R')}",
        "",
        f"{h.name} INT: {h.player_at('INT1')}|{h.player_at('INT2')}",
        f"{a.name} INT: {a.player_at('INT1')}|{a.player_at('INT2')}",
    ]
    lineup = "\n".join(lines)

    with open("Commentary.txt", "w", encoding="utf-8") as f:
        f.write(header + lineup + "\n\n")


def append_commentary_line(text: str) -> None:
    """Append a single line to Commentary.txt."""
    with open("Commentary.txt", "a", encoding="utf-8") as f:
        f.write(text + "\n")


def write_weather_commentary(weather: str) -> None:
    with open("Commentary.txt", "a", encoding="utf-8") as f:
        f.write(f"Conditions: {weather}\n")


def write_end_of_quarter(ms: MatchState) -> None:
    home_line = f"{ms.home.name}: {ms.home_goals}.{ms.home_behinds}.{ms.home_score}"
    away_line = f"{ms.away.name}: {ms.away_goals}.{ms.away_behinds}.{ms.away_score}"
    block = (
        "[COLOR=rgb(61, 142, 185)]"
        "====================\n"
        f"END OF QUARTER {ms.qtr - 1}\n"
        f"{home_line}\n{away_line}\n"
        "===================="
        "[/COLOR]"
    )
    append_commentary_line(block)


def write_score_update(ms: MatchState) -> None:
    home_line = f"{ms.home.name}: {ms.home_goals}.{ms.home_behinds}.{ms.home_score}"
    away_line = f"{ms.away.name}: {ms.away_goals}.{ms.away_behinds}.{ms.away_score}"
    block = (
        "[COLOR=rgb(61, 142, 185)]"
        "--------------------\n"
        f"{home_line}\n{away_line}\n"
        "--------------------"
        "[/COLOR]"
    )
    append_commentary_line(block)


def write_interchange_commentary(ms: MatchState, on_name: str, off_name: str, team_name: str, other_bench_name: str) -> None:
    """Append an interchange commentary line to Commentary.txt."""
    colour_start = "[COLOR=rgb(209, 72, 65)]"
    colour_end = "[/COLOR]"
    if on_name == off_name:
        msg = f"<<< Meanwhile over on the bench {on_name} is getting some treatment >>>"
    elif off_name == other_bench_name:
        msg = f"<<< They're playing musical chairs on the {team_name} bench as {on_name} and {off_name} switch seats>>>"
    else:
        msg = f"<<<ON: {on_name} | OFF: {off_name}>>>"
    append_commentary_line(f"{colour_start}{msg}{colour_end}")


# ---------------------------------------------------------------------------
# Head-to-head summary (appended to Commentary.txt at match end)
# ---------------------------------------------------------------------------

def write_h2h_report(ms: MatchState) -> None:
    # finalise end times for matchups still active at full-time
    total = sum(ms.q_lengths)
    for mu_data in ms.h2h_data.values():
        if mu_data["End"] == 0:
            mu_data["End"] = total

    lines = ["\n\n\nMatch-Ups"]
    for mu, data in ms.h2h_data.items():
        outcome = data["Outcome"]
        if -2 <= outcome <= 2:
            comment = f"In a tough battle, {mu[0]} and {mu[1]} were more or less evenly matched."
        elif 3 <= outcome <= 5:
            comment = f"In an enthralling match up, {mu[0]} has prevailed over {mu[1]}"
        elif 6 <= outcome <= 8:
            comment = f"No ambiguity on who won this matchup, {mu[0]} well and truly has {mu[1]}'s measure."
        elif outcome >= 9:
            comment = f"It's been The {mu[0]} Show today as the superstar made {mu[1]} look like an insignificant speck of dust."
        elif -5 <= outcome <= -3:
            comment = f"In an enthralling match up, {mu[1]} has prevailed over {mu[0]}"
        elif -8 <= outcome <= -6:
            comment = f"No ambiguity on who won this matchup, {mu[1]} well and truly has {mu[0]}'s measure."
        elif outcome <= -9:
            comment = f"It's been The {mu[1]} Show today as the superstar made {mu[0]} look like an insignificant speck of dust."
        else:
            comment = ""
        lines.append(f"{mu}; {data['Start']} to {data['End']}; {comment}")

    with open("Commentary.txt", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Interchange log CSV
# ---------------------------------------------------------------------------

_INT_FIELDS = ["QTR", "TIME", "PLAYER", *STAT_CATEGORIES, "TEAM", "POSITION"]


def init_interchange_log() -> None:
    with open("InterchangeLog.csv", "w", newline="\n", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=_INT_FIELDS).writeheader()


def write_interchange_row(ms: MatchState) -> None:
    """Write two rows (ON/OFF) to InterchangeLog.csv."""
    team = ms.active_team()
    on_name = team.pos_players[ms.key_on]
    off_name = team.pos_players[ms.key_off]

    def _row(label: str, player: str, pos_key: str) -> dict:
        s = team.stats[player]
        return {
            "QTR": str(ms.qtr),
            "TIME": ms.display_time,
            "PLAYER": f"{label}: {player}",
            **{cat: str(s[cat]) for cat in STAT_CATEGORIES},
            "TEAM": team.name,
            "POSITION": pos_key,
        }

    with open("InterchangeLog.csv", "a", newline="\n", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_INT_FIELDS)
        writer.writerow(_row("ON", on_name, ms.key_on))
        writer.writerow(_row("OFF", off_name, ms.key_off))


# ---------------------------------------------------------------------------
# End-of-quarter score CSV row (appended to PlayerStats.csv)
# ---------------------------------------------------------------------------

def write_quarter_score_row(ms: MatchState) -> None:
    with open("PlayerStats.csv", "a", newline="\n", encoding="utf-8") as f:
        w = csv.writer(f)
        if ms.qtr - 1 == 1:
            w.writerow([
                "QTR",
                f"{ms.home.name} G", f"{ms.home.name} B", f"{ms.home.name} S",
                f"{ms.away.name} G", f"{ms.away.name} B", f"{ms.away.name} S",
            ])
        w.writerow([
            ms.qtr - 1,
            ms.home_goals, ms.home_behinds, ms.home_score,
            ms.away_goals, ms.away_behinds, ms.away_score,
        ])
        if ms.qtr - 1 == 4:
            w.writerow(["\n"])


# ---------------------------------------------------------------------------
# Full stat reports (end of match)
# ---------------------------------------------------------------------------

def generate_stat_reports(ms: MatchState) -> None:
    """Write PlayerStats.csv, TeamStats.csv, Form.csv, Scoring Summary.txt."""
    write_player_stat_exports(ms)
    if pd is None:
        print("[reports] pandas not available – skipping stat reports")
        return

    # Player stats
    full_stats = {**ms.home.stats, **ms.away.stats}
    df = pd.DataFrame(full_stats).transpose()
    df.to_csv("PlayerStats.csv", mode="a")

    # Team totals
    n_home = len(ms.home.players)
    df_home = df.iloc[:n_home]
    df_away = df.iloc[n_home:]
    team_df = pd.concat([df_home.sum(), df_away.sum()], axis=1)
    team_df.columns = [ms.home.name, ms.away.name]
    team_df.to_csv("TeamStats.csv")

    # Form / Best-on-Ground
    full_form = {**ms.home.player_form, **ms.away.player_form}
    form_df = pd.DataFrame(full_form, index=["Form"]).transpose()
    form_df["player"] = form_df.index
    form_df = form_df.sample(frac=1, random_state=0).sort_values(by="Form", ascending=False)
    three_votes = form_df.iat[0, 1]
    two_votes = form_df.iat[1, 1]
    one_vote = form_df.iat[2, 1]
    form_df.to_csv("Form.csv")

    # 3-2-1 votes
    with open("PlayerStats.csv", "a", newline="\n", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["\n"])
        w.writerow(["VOTES"])
        w.writerow([3, 2, 1])
        w.writerow([three_votes, two_votes, one_vote])

    # Scoring summary
    with open("Scoring Summary.txt", "w", encoding="utf-8") as f:
        f.write("SCORING SUMMARY\n")
        for line in ms.scoreboard_log:
            f.write(line + "\n")
