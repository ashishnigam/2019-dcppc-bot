AWARDEE_TO_TEAM = {
    "White": "Team-Phosphorus",
    "Brown": "Team-Copper",
    "Foster": "Team-Argon",
    "Kohane": "Team-Carbon",
    "Paten": "Team-Calcium",
    "Ahalt": "Team-Helium",
    "Ma'ayan": "Team-Nitrogen",
    "Ohno-Machado": "Team-Oxygen",
    "Crosas": "Team-Sodium",
    "Davis-Dusenbery": "Team-Xenon",
    "NIH": "Team-Hydrogen"
    }


KC_STRING_TO_KC_LABEL = \
{'Full Stacks Working Group': 'full-stacks',
 'KC1 FAIR guidelines and metrics': 'KC1-fair',
 'KC2 GUIDs': 'KC2-guids',
 'KC2 GUIDs and KC3 API': 'KC2-guids',
 'KC3 API Best Practices': 'KC3-apis',
 'KC3 Open APIs': 'KC3-apis',
 'KC3 Open APIs/KC6 Research, Ethics, Privacy, Security': 'KC3-apis',
 'KC4 Cloud Agnostic Architectures': 'KC4-cloud',
 'KC5 Workspaces': 'KC5-workspaces',
 'KC6 Research, Ethics, Privacy, Security': 'KC6-ethics',
 'KC7 Indexing and Search': 'KC7-search',
 'KC8 Use Cases': 'KC8-use-cases',
 'KC9 Coordination & Outreach': 'KC9-training',
 'KC9 Coordination and Training': 'KC9-training',
 'Reporting': None}


LABELS = {
    "started": "4c9f70",
    "no team": "f9dbbd",
    "Team-Helium": "f9dbbd",
    "Team-Xenon": "fca17d",
    "Team-Argon": "da627d",
    "Team-Carbon": "9a348e",
    "Team-Nitrogen": "0d0628",
    "Team-Oxygen": "8ea4d2",
    "Team-Calcium": "6279b8",
    "Team-Phosphorus": "49516f",
    "Team-Copper": "496f5d",
    "Team-Sodium": "4c9f70",
    "Team-Hydrogen": "cd5d67",
    "KC1-fair": "410b13",
    "KC2-guids": "cd5d67",
    "KC3-apis": "ba1f33",
    "KC4-cloud": "421820",
    "KC5-workspaces": "421820",
    "KC6-ethics": "012622",
    "KC7-search": "003b36",
    "KC8-use-cases": "e98a15",
    "KC9-training": "59114d",
    "full-stacks": "59114d",
}


def fetch_issues_by_repo(github_client, repo):
    for issue in repo.get_issues(state='open'):
        yield issue
    for issue in repo.get_issues(state='closed'):
        yield issue


def extract_milestone_info(issue):
    try:
        issue_id_line = next(
            line
            for line in issue.body.split("\n")
            if line.startswith("milestone:")
        )
        issue_id = issue_id_line.split()[-1]
    except StopIteration:
        issue_id = None

    info = {
        "id": issue_id,
        "title": issue.title,
        "body": issue.body,
        "issue_number": issue.number,
        "teams": [label.name for label in issue.labels],
        "state": issue.state,
        "issue_obj": issue,
    }

    return info
