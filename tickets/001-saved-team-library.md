# CF-001: Save and reuse teams across app sessions

Status: Ready for implementation

## User story

As a Couch Footy player, I want to save teams I enter and select them when I next open the app, so I do not have to enter the same roster again.

## Current behaviour

The app loads both match teams from TeamSelection.csv (or the legacy XLS fallback). It has no library of individually saved teams and no saved-team picker. The existing CSV remains an entry channel.

## Proposed behaviour

- Offer a Save Team action for each successfully loaded or entered team, including teams loaded through the existing CSV channel.
- Save each team independently, so it can play as home or away against another saved or newly entered team.
- Before starting a match, offer a Saved Teams picker for each side. Show the team name and a roster preview, and allow selection without re-entering players.
- Preserve team name, all 20 players, positions, roster order, and all seven player attributes exactly.
- Keep season, round, and match ID in match setup; these are not properties of a saved team.
- Show clear save success or failure feedback. A failed save must not be reported as successful or prevent the player from continuing with the entered team.
- When saving changes to an existing saved team, offer Update Team or Save as New. Never silently replace a different team because its name matches.

## Storage decision

Use one versioned JSON file per team in a dedicated saved_teams directory beside the executable (or in the project root for source runs), following the app's existing writable-folder convention. Create the directory on first save.

JSON represents a team's metadata and ordered players directly, supports future entry channels, and uses Python's standard library. At this roster size, performance and file-size differences from CSV are negligible; preserving structure is the deciding factor.

Each record contains schema_version, a generated stable team ID, team name, and an ordered players array. Each player contains name, position, and attributes: strength, speed, agility, skill, endurance, pressure, and aura. Use the generated ID as the filename rather than user-entered team names. Write through a temporary file and atomically replace the destination to protect existing saves from interrupted writes.

Keep persistence separate from CSV loading and the selection UI. All current and future entry channels should pass through the same validation and team-saving interface.

## Acceptance criteria

1. A player can load teams using the current CSV workflow and explicitly save either team independently.
2. After fully closing and reopening Couch Footy, saved teams appear in the picker without requiring the original CSV roster.
3. Selecting a saved team restores its name, 20 players, positions, order, and every attribute without changes.
4. Saved teams can be selected independently for home and away; a saved team can also play against a newly entered team.
5. Existing roster and attribute validation applies when saving and loading. Match setup also enforces the current unique-player-name rule across both selected teams and explains any conflicts before play starts.
6. Multiple teams can be stored. Teams with matching display names cannot accidentally overwrite one another and are distinguishable in the picker.
7. Updating an existing team persists its changes after restart; saving as new preserves the original.
8. A missing or empty saved_teams directory produces a helpful empty state and allows the existing entry workflow to continue.
9. A malformed or unsupported saved file is identified and skipped without preventing valid teams from being selected. The file is preserved for recovery.
10. Permission errors and interrupted writes leave existing saves intact and display a useful error.
11. Storage uses a stable app-relative path in both source and packaged builds, independent of the shell's working directory.

## Verification

- Automated save/load round trips covering all roster fields, Unicode names, multiple teams, and update versus save-as-new behaviour.
- Tests for invalid records, unsupported schema versions, cross-team duplicate names, and failed writes preserving an existing save.
- Manual source-app check: save two teams, exit, reopen, select both, and start a match.
- Repeat the restart and selection check in a rebuilt Windows executable.

## Scope boundary

This first ticket delivers local persistence and selection. Cloud sync, accounts, additional import channels, and sharing are future work. The common team model and persistence interface provide the foundation for those channels.
