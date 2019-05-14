#! /usr/bin/env python
import argparse
from datetime import datetime
import json
import logging
import os
import sys
import time
import math

from github import Github
from github.GithubException import UnknownObjectException
import pandas as pd

from utils import AWARDEE_TO_TEAM, LABELS, KC_STRING_TO_KC_LABEL
from utils import fetch_issues_by_repo, extract_milestone_info


# Set up logging
logFormatter = logging.Formatter("[%(levelname)-8s] %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)


def create_labels(repo, labels):
    """
    For each label in LABELS, make sure that label exists in 
    repo's list of labels. This action happens at the 
    repository scope.
    """
    current_labels = {label.name: label for label in repo.get_labels()}
    for label, color in labels.items():
        if label not in current_labels:
            repo.create_label(label, color)
        else:
            # Update color
            this_label = repo.get_label(label)
            this_label.edit(label, color)


def create_issue_body_milestone(info):
    """
    Return a string containing the text that will become
    a milestone issue.
    """
    record_number = info["Record Number"]
    title = info["Task"]
    description = info["Description"]
    due_date = info["Revised Due Date"]

    try:
        if math.isnan(due_date):
            due_date = 'none specified'
    except TypeError:
        pass
        
    try:
        if math.isnan(description):
            description = '*no description available*'
    except TypeError:
        pass

    return """\
# {}

{}

milestone: {}
due date: {}
""".format(title, description, record_number, due_date)


def create_issue(repo, title, body, *, labels=None, change_github=False):
    """
    Create an issue in repo with the given title and description.
    """
    if labels is None:
        labels = []
    if change_github:
        return repo.create_issue(title, body, labels=labels)


def update_issue(repo, issue, *, body=None, labels=None, title=None, change_github=False):
    """
    Update the body/title/labels of the specified milestone issue
    in the specified repository.
    """
    if labels is None:
        labels = []
    labels = list(labels)

    if title is None:
        title = issue.title
    if change_github:
        issue.edit(body=body, title=title, labels=labels)

    return issue

def set_log_level_from_verbose(args):
    """
    Use the user-provided --verbose flag to set the level of logging
    """
    if not args.verbose:
        consoleHandler.setLevel(logging.ERROR)
    elif args.verbose == 1:
        consoleHandler.setLevel(logging.WARNING)
    elif args.verbose == 2:
        consoleHandler.setLevel(logging.INFO)
    elif args.verbose >= 3:
        consoleHandler.setLevel(logging.DEBUG)
    else:
        consoleHandler.setLevel(logging.ERROR)


def save_issues(milestones, filepath):
    """
    Initialize an empty dictionary. For each milestone issue,
    extract everything except the PyGithub Issue object,
    and save it all to an external JSON file at filepath.
    """
    to_save = {"milestones": {}}
    for key, item in milestones.items():
        new_item = item.copy()
        del new_item["issue_obj"]
        to_save["milestones"][key] = new_item

    with open(filepath, "wt") as f:
        json.dump(to_save, f)


def add_common_args(parser):
    """
    Parse command line arguments
    """
    parser.add_argument('-f', '--force', action='store_true',
                        help='force big changes.')
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="verbose level... repeat up to three times.",
    )
    parser.add_argument(
        "-m",
        "--milestones",
        help="milestones repo name",
        default="dcppc/dcppc-milestones",
    )
    parser.add_argument(
        "--change-github",
        help="do the writing to GitHub API",
        action="store_true",
        default=False,
    )
    parser.add_argument("--token", help="GitHub auth token", type=str, default="")

    parser.add_argument(
        "-b",
        "--backup",
        help="Current GitHub issue data will be saved to this file",
        type=str,
    )


def bulk_create_issues(repo, target):
    """
    Create multiple placeholder issues in the repository
    """
    issue = create_issue(repo, "PLACEHOLDER", "")
    while issue.number < target:
        issue = create_issue(repo, "PLACEHOLDER", "")
        logging.debug("Bulk-created issue {issue.number}")
    return issue


def restore(g, args):
    """
    Back up issues in deliverables and milestones to a file, and then restore
    the deliverable and milestone issues from a file.
    """
    # You should not use this method
    assert 0

    # STEP 1: 
    # read data from github issues, back it up

    milestone_repo = g.get_repo(args.milestones)
    deliverables_repo = g.get_repo(args.deliverables)
    milestone_issues, deliverables_issues = backup_issues(
        g, milestone_repo, deliverables_repo, args.backup
    )

    # STEP 2:
    # read data from backup file

    # load and sort milestone issues by issue number
    data = json.load(args.backup_file)
    items = sorted(
        data["milestones"], key=lambda k: data["milestones"][k]["issue_number"]
    )

    for milestone_id in items:
        # get milestone issue info from backup file
        info = data["milestones"][milestone_id]
        try:
            issue = milestone_repo.get_issue(info["issue_number"])
        except UnknownObjectException:
            if not args.change_github:
                # We can't do the loop in this case, just skip.
                continue

            # Issue doesn't exist yet, we need to create empty ones to get the
            # right issue number
            issue = bulk_create_issues(milestone_repo, int(info["issue_number"]))

        # issue already exits, let's update it
        labels = {label.name for label in issue.labels}
        if (
            issue.title != info["title"]
            or issue.body != info["body"]
            or labels != set(info["teams"])
        ):
            logging.info(f"Need to update {info['issue_number']}")
            print(issue.body == info["body"],
                  labels == set(info["teams"]),
                  issue.title == info["title"])
            update_issue(
                milestone_repo,
                issue,
                body=info["body"],
                title=info["title"],
                labels=info["teams"],
                change_github=args.change_github,
            )
        else:
            logging.debug(f"Already up to date {info['issue_number']}")

    # make sure the repository has all the labels
    create_labels(deliverables_repo, LABELS)

    # load and sort deliverables issues by issue number
    items = sorted(
        data["deliverables"], key=lambda k: data["deliverables"][k]["issue_number"]
    )
    for deliverable_id in items:
        info = data["deliverables"][deliverable_id]
        try:
            issue = deliverables_repo.get_issue(info["issue_number"])
        except UnknownObjectException:
            if not args.change_github:
                # We can't do the loop in this case, just skip.
                continue

            # Issue doesn't exist yet, we need to create empty ones to get the
            # right issue number
            issue = bulk_create_issues(deliverables_repo, int(info["issue_number"]))

        # issue already exits, let's update it
        labels = {label.name for label in issue.labels}
        if (
            issue.title != info["title"]
            or issue.body != info["body"]
            or labels != set(info["teams"])
        ):
            logging.info(f"Need to update {info['issue_number']}")
            update_issue(
                deliverables_repo,
                issue,
                body=info["body"],
                title=info["title"],
                labels=info["teams"],
                change_github=args.change_github
            )
        else:
            logging.debug(f"Already up to date {info['issue_number']}")


def backup_issues(g, milestone_repo, backup_file):
    """
    Back up all issues in a given repository into an external JSON file.
    """
    milestone_issues = {}
    for issue in fetch_issues_by_repo(g, milestone_repo):
        info = extract_milestone_info(issue)
        if info["id"]:
            if info["id"] in milestone_issues:
                print('ERROR, duplicate milestone ID {}'.format(info["id"]))
            milestone_issues[info["id"]] = info

    save_issues(milestone_issues, backup_file)

    return milestone_issues


def update(g, args):
    """
    Back up all the Github issues in a repo, then update each issue
    in the repo using the milestones CSV file.
    """

    # STEP 1: 
    # read data from github issues, back it up

    milestone_repo = g.get_repo(args.milestones)
    milestone_issues = backup_issues(
        g, milestone_repo, args.backup
    )

    # STEP 2:
    # read local data from spreadsheets,
    # check if updates are needed
    # and update github issues

    milestone_data = pd.read_csv(args.milestones_csv)

    # make sure the repository has all the labels
    create_labels(milestone_repo, LABELS)

    # list of issues to update
    update_list = []

    seen = set ()
    for i, info in milestone_data.iterrows():
        milestone_id = str(info["Record Number"])

        if milestone_id in seen:
            print('SKIPPING duplicate milestone_id {} ({})'.format(milestone_id, info["Awardee"]))
            continue
        seen.add(milestone_id)

        # Get the awardee for this milestone
        awardee = info['Awardee']

        # Check if awardee is empty (nans because pandas)
        isnan = False
        try:
            if math.isnan(awardee):
                isnan = True
        except TypeError:
            pass

        # Start by assuming the milestone has no team
        labels = set(['no team'])

        # If the awardee is empty, print a warning and continue.
        # Otherwise, make sure the awardee is in our map of 
        # awardees to teams (e.g., Brown --> Copper)
        if isnan:
            print('WARNING missing awardee for {} ({})'.format(milestone_id, info['Awardee']))
            assert 0
        else:
            awardee = awardee.strip()
            assert awardee in AWARDEE_TO_TEAM, (awardee,)
            team_label = AWARDEE_TO_TEAM[awardee]
            labels = { team_label }

        # maybe add KC labels here:
        kc = info["Key Capability"]
        kc = str(kc).strip()
        if KC_STRING_TO_KC_LABEL.get(kc):
            label = KC_STRING_TO_KC_LABEL[kc]
            labels.add(label)

        body = create_issue_body_milestone(info)
        if milestone_id not in milestone_issues:
            logging.info(f"create issue {milestone_id}")
            if not args.force:
                logging.error("should not be creating issues!? use -f if expected")
                assert 0, "use -f if we are expected to be creating issues"

            title = info["Task"]
            issue = create_issue(milestone_repo, title, body, labels=labels, change_github=args.change_github)

            if args.change_github:
                info = extract_milestone_info(issue)
                milestone_issues[milestone_id] = info
            else:
                logging.info("not actually changing github -- use --change-github to do that.")
        else:
            title = info["Task"]
            issue = milestone_issues[milestone_id]
            current_labels = set(issue["teams"])
            labels = set(labels)

            # only _add_ labels, do not remove.
            if issue["body"] != body or not labels.issubset(current_labels) \
                  or title != issue["title"]:
                if not current_labels.issubset(labels):
                    labels.update(current_labels)

                # make sure we check for a frustrating bug :)
                if 'started' in current_labels:
                    assert 'started' in labels

                logging.info(f"Need to update {milestone_id}")
                logging.debug(f"old body: {issue['body']}")
                logging.debug(f"new body: {body}")
                update_list.append((issue["issue_obj"], title, body, labels))

    if update_list:
        if len(update_list) > 10 and not args.force:
            logging.error(f"Too many issues to update without --force {len(update_list)}; quitting.")
            sys.exit(-1)

        for issue_obj, title, body, labels in update_list:
            issue = update_issue(
               milestone_repo, issue_obj, title=title, body=body, labels=labels, change_github=args.change_github
        )


def main():
    """
    Parse arguments from the user, and use them to decide
    what mode to run the DCPPC bot in.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_update = subparsers.add_parser(
        "update", help="Update files based on local spreadsheets"
    )
    parser_update.add_argument('milestones_csv')
    add_common_args(parser_update)
    parser_update.set_defaults(func=update)

    parser_restore = subparsers.add_parser(
        "restore", help="Restore files from a local backup"
    )
    add_common_args(parser_restore)
    parser_restore.add_argument(
        "backup_file",
        help="Previous backup to be restored",
        type=argparse.FileType("rt"),
    )
    parser_restore.set_defaults(func=restore)

    args = parser.parse_args()
    if not vars(args):
        parser.print_help()
        sys.exit(1)

    set_log_level_from_verbose(args)
    logging.info(f"info")
    logging.warning(f"warning")
    logging.debug(f"debug")

    if args.token:
        g = Github(args.token)
    else:
        # Try to read the GITHUB_TOKEN env var
        try:
            g = Github(os.environ["GITHUB_TOKEN"])
        except KeyError:
            logging.error(
                "Please provide a GitHub auth token using --token "
                "or the GITHUB_TOKEN env var"
            )
            sys.exit(1)

    if args.backup is None:
        os.makedirs("backups", exist_ok=True)
        now = datetime.utcnow().isoformat()
        args.backup = os.path.join("backups", f"backup_{now}.json")

    args.func(g, args)


if __name__ == "__main__":
    main()
