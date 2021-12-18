import pandas as pd
import numpy as np
import requests
import json


# Google Sheets document and sheet id
SHEET_VJUDGE = ('1vSAxQ5Idg0usQpud3OpXqZm3HgfIeZT4g8V3a-sJLWA', '737892149')
SHEET_SIM1 = ('1Wzgyra6nsrPUo1zvl0yYZwKKpccYBIR6y6ihtMgRkgU', '1771707662')
SHEET_SIM2 = ('1U5BADLoNBwwFI3qJE3LrDYfUzRRIdnwaqUTA5geBvlE', '1497459820')


# builds an URL to download the sheet based on the doc and sheet id
def build_sheet_url(doc_id, sheet_id):
    return f'https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={sheet_id}'


# make a request and return the response
def make_requests(url, params=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-Requested-With': 'XMLHttpRequest',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'TE': 'trailers',
    }

    try:
        response = requests.get(url=url, headers=headers, params=params)
    except Exception as e:
        print(f'Error: {e.args}')
        return None

    if response.status_code == 200:
        return response
    return None


# get contest list (name and id)
def get_contests():
    params = (
        ('draw', '1'),
        ('start', '0'),
        ('length', '100'),
        ('sortDir', 'asc'),
        ('sortCol', '4'),
        ('category', 'all'),
        ('running', '0'),
        ('title', 'SCC0211'),
    )
    url = 'https://vjudge.net/contest/data'
    response = make_requests(url, params)
    if response is None:
        print('Error parsing contests')
        exit(1)

    return json.loads(response.text)['data']


# retrieves all the problems solved bu handle from some contest
def get_submissions(contest_id):
    response = make_requests(f'https://vjudge.net/contest/rank/single/{contest_id}')
    if response is None:
        print('Error parsing submissions')
        exit(1)

    contest_info = json.loads(response.text)

    handle_subs = dict()
    for submission in contest_info['submissions']:
        if submission[2] == 1:
            user_id = submission[0]
            problem_id = submission[1]
            handle = contest_info['participants'][str(user_id)][0].lower()

            if handle_subs.get(handle) is None:
                handle_subs[handle] = set()
            handle_subs[handle].add(problem_id)
    return handle_subs


# update the submission of all team members according to the handle that actually submitted them in the contest
def update_team(df_sheet, contest_name, all_subs):
    df = pd.read_csv(build_sheet_url(*df_sheet))
    for index, row in df.iterrows():
        cur_handle = row['handle'].lower()
        if all_subs[contest_name].get(cur_handle) is None:
            print(f"[Contest Warning]: user {cur_handle} didn't participate contest {contest_name}.")
            continue

        for new_nusp in [row['nusp1'], row['nusp2'], row['nusp3']]:
            if np.isnan(new_nusp):
                continue

            new_nusp = int(new_nusp)
            # add all submissions from cur_handle to new_handle nusp
            if nusp_to_handle.get(new_nusp):
                new_handle = nusp_to_handle[new_nusp]
                if all_subs[contest_name].get(new_handle) is None:
                    all_subs[contest_name][new_handle] = set()
                all_subs[contest_name][new_handle] |= all_subs[contest_name][cur_handle]
            else:
                print(f"[NUSP Warning]: {new_nusp} didn't answer the forms and is listed under a team.")


# generate the csv
if __name__ == '__main__':
    all_handles = set()
    all_contests = set()
    all_subs = dict()

    # get list of submissions, handles and contests
    for contest in get_contests():
        print(contest[1], '-', f'https://vjudge.net/contest/{contest[0]}')
        submissions = get_submissions(contest[0])

        all_subs[contest[1]] = submissions
        all_contests.add(contest[1])
        all_handles |= submissions.keys()

    # maps nusp with handle
    nusp_to_handle = dict()
    df_nusp = pd.read_csv(build_sheet_url(*SHEET_VJUDGE))
    for index, row in df_nusp.iterrows():
        cur_handle = row['handle'].lower()
        if not cur_handle in all_handles:
            print(f'User {cur_handle} did not participate in ANY contest...')
        nusp_to_handle[int(row['nusp'])] = cur_handle

    # update score on team contests
    update_team(SHEET_SIM1, 'SCC0211 - Simulado 1', all_subs)
    update_team(SHEET_SIM2, 'SCC0211 - Simulado 2', all_subs)

    # update score for each contest
    df = pd.DataFrame(index=sorted(all_handles), columns=sorted(all_contests))
    for contest, submissions in all_subs.items():
        for handle, submission in submissions.items():
            df.at[handle, contest] = len(submission)

    # add nusp column
    for nusp, handle in nusp_to_handle.items():
        df.at[handle, 'N.USP'] = nusp
    df.fillna(0, inplace=True)
    df = df.astype({'N.USP': int})
    df = df[['N.USP', *df.columns.values[:-1]]]

    # add grading
    contest_list = [name for name in df.columns if "SCC0211" in name and "Simulado" not in name]
    df['Ex.Semanais'] = df[contest_list].sum(numeric_only=True, axis=1)

    contest_list = [name for name in df.columns if "SCC0211" in name and "Simulado" in name]
    df['Ex.Simulado'] = df[contest_list].sum(numeric_only=True, axis=1)

    # rename columns to erase 'SCC0211' from them
    contest_list = [name for name in df.columns if "SCC0211" in name]
    df = df.rename(dict([(name, name[10:]) for name in contest_list]), axis=1)

    # generate csv
    df.to_csv('Notas.csv')
