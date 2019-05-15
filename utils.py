AWARDEE_TO_TEAM = {
    "White": "Team-Phosphorus",
    "Brown": "Team-Copper",
    }


KC_STRING_TO_KC_LABEL = \
{'KC1 FAIR guidelines and metrics': 'KC1-fair',
 'KC9 Coordination & Outreach': 'KC9-training',
 'KC9 Coordination and Training': 'KC9-training'}

LABELS = {
    "started": "4c9f70",
    "no team": "f9dbbd",
    "Team-Phosphorus": "49516f",
    "Team-Copper": "496f5d",
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
