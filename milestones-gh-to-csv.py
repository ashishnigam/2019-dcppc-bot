#! /usr/bin/env python
import argparse
from datetime import datetime
import json
import logging
import os
import sys
import time
import math
import csv

from github import Github
from github.GithubException import UnknownObjectException
import pandas as pd


from utils import AWARDEE_TO_TEAM, LABELS
from utils import fetch_issues_by_repo, extract_milestone_info


# Set up logging
logFormatter = logging.Formatter("[%(levelname)-8s] %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)


def set_log_level_from_verbose(args):
    if not args.verbose:
        consoleHandler.setLevel("ERROR")
    elif args.verbose == 1:
        consoleHandler.setLevel("WARNING")
    elif args.verbose == 2:
        consoleHandler.setLevel("INFO")
    elif args.verbose >= 3:
        consoleHandler.setLevel("DEBUG")
    else:
        consoleHandler.setLevel("ERROR")


def get_status_from_gh(record):
    status = "Not Started"
    if 'started' in record["teams"]:
        status = 'In Progress'
    if record["state"] == "closed":
        status = "Finished"
    return status


def isnull(field):
    isnan = False
    try:
        if math.isnan(field):
            return True
    except TypeError:
        pass
    return False


def null_to_default(field, default=''):
    if isnull(field):
        return default
    else:
        return field


def get_awardee_from_csv(info):
    # labels!
    awardee = info['Awardee']

    if isnull(awardee):
        return None

    return awardee


def load_gh_and_csv(g, args):
    print('loading from gh')
    ## STEP 1: read data from github issues, back it up
    milestone_repo = g.get_repo(args.milestones)
    milestone_gh = {}
    for issue in fetch_issues_by_repo(g, milestone_repo):
        info = extract_milestone_info(issue)
        if not info["id"]:
            print('WARNING: skipping bc no ID, issue', info["issue_number"])
        else:
            milestone_gh[info["id"]] = info

    ## STEP 2:
    ## read local data from spreadsheets,

    print('loading from CSV')
    milestone_data = pd.read_csv(args.milestones_csv)

    seen = set()
    milestone_d = {}
    for i, info in milestone_data.iterrows():
        milestone_id = str(info["Record Number"])

        if milestone_id in seen:
            print('SKIPPING duplicate milestone_id {} ({})'.format(milestone_id, info["Awardee"]))
            continue
        seen.add(milestone_id)

        milestone_d[milestone_id] = info

    ## check versus each other?
    github_ids = set(milestone_gh)
    csv_ids = set(milestone_d)

    if github_ids - csv_ids:
        print('in github, not in CSV:', github_ids - csv_ids)
        assert 0

    if csv_ids - github_ids:
        print('in csv, not in github:', csv_ids - github_ids)
        assert 0

    return milestone_gh, milestone_d


def extract_report(milestone_gh, milestone_d, outfp, select_awardee=None):
    w = csv.DictWriter(outfp, fieldnames=['milestone_id',
                                          'status',
                                          'due_date',
                                          'task',
                                          'awardee',
                                          'kc',
                                          'github_issue_url'])
    w.writeheader()

    for milestone_id in milestone_gh:
        status = get_status_from_gh(milestone_gh[milestone_id])
        awardee = get_awardee_from_csv(milestone_d[milestone_id])
        issue_number = milestone_gh[milestone_id]["issue_number"]

        github_url = f"https://github.com/dcppc/dcppc-milestones/issues/{issue_number}"

        if not select_awardee or awardee == select_awardee:
            record = milestone_d[milestone_id]

            d = dict(milestone_id=milestone_id,
                     status=status, awardee=awardee,
                     task=record['Task'],
                     due_date=null_to_default(record['Revised Due Date']),
                     kc=record['Key Capability'],
                     github_issue_url=github_url)

            w.writerow(d)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output-prefix',
                        default='report-team-', help='output filename prefix')
    parser.add_argument('milestones_csv', default='../dcppc-project-management/phase-1/milestones.csv')
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
    parser.add_argument("--token", help="GitHub auth token", type=str, default="")

    args = parser.parse_args()
    if not vars(args):
        parser.print_help()
        sys.exit(1)

    set_log_level_from_verbose(args)

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

    milestone_gh, milestone_d = load_gh_and_csv(g, args)

    for select_awardee in AWARDEE_TO_TEAM:
        print('building report for {}...'.format(select_awardee))
        report_name = args.output_prefix + select_awardee + '.csv'
        print('... in {}'.format(report_name))
        with open(report_name, 'wt') as outfp:
            extract_report(milestone_gh, milestone_d,
                           outfp, select_awardee=select_awardee)


if __name__ == "__main__":
    main()
