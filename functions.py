import selenium.common.exceptions
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from datetime import datetime
import time
import logging
import os


# create files and logging folder if they don't exist
filepath = 'files'
if not os.path.exists(filepath):
    os.makedirs(filepath)
filepath2 = 'files/logging'
if not os.path.exists(filepath2):
    os.makedirs(filepath2)

# configure log
logging.basicConfig(
    filename="files/logging/last_run.log",
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


# create driver and configure options
options = webdriver.ChromeOptions()
# doesn't display browser when running, can comment out
options.add_argument("--headless=new")
browser = webdriver.Chrome(options=options)


def print_err(message):
    yellow = '\033[93m'
    off = '\033[0;0m'
    print(yellow + message + off)


# get the tables from case page
def get_tables(case_num):
    # wait 10 seconds for tables to load, webdriverwait.until expected condition intermittently caused driver to crash.
    timeout = 10
    wait = 0
    tables = []
    while not tables:
        # get list of tables
        tables = browser.find_elements(By.CLASS_NAME, "tableback")
        if tables:
            break
        wait += 1
        time.sleep(1)
        # returns error and quits if tables not found
        if wait >= timeout:
            now = datetime.now().strftime('%d-%m-%y-%H-%M-%S')
            browser.save_screenshot(f'files/logging/err_{now}.png')
            logging.critical(f'Error: Tables not found for case {case_num}')
            print_err(f'Error: Tables not found for case {case_num}')
            exit(1)
    return tables


def get_table_data(table_name, tables, case_num):
    data = []
    for table in tables:
        # find element by subheader table name
        try:
            sub_header = table.find_element(By.CLASS_NAME, 'subheader')
        except NoSuchElementException:
            # log if table name not found
            logging.warning(f'Subheader "{table_name}" not found for case {case_num}')
            print_err(f'    Warning: Subheader "{table_name}" not found for case {case_num}')
            # return empty list if table not found
            return []
        if sub_header.text == table_name:
            # expand collapsed tables
            if sub_header.text == 'Service/Process' or sub_header.text == 'Reports' \
                    or sub_header.text == 'Garnishment Information':
                sub_header.click()
            # return grid items
            grid_items = table.find_elements(By.CSS_SELECTOR, 'td.labelvaluegridright, td.labelvaluegridtopright')
            for row in grid_items:
                data.append(row.text.strip())

            # return row items
            rows = table.find_elements(By.CSS_SELECTOR, 'tr.gridrow, tr.gridalternaterow')
            if rows:
                for row in rows:
                    row_list = []
                    tds = row.find_elements(By.CSS_SELECTOR, 'td')
                    for td in tds:
                        row_list.append(td.text.strip())
                    data.append(row_list)
            return data
    return []


# move browser to case, unused in main scraper
def go_to_case(case_num):
    time.sleep(.5)
    case_num_search_url = 'https://eapps.courts.state.va.us/gdcourts/criminalCivilCaseSearch.do?fromSidebar=true' \
                          '&formAction=searchLanding&searchDivision=V&searchFipsCode=510&curentFipsCode=510'
    while browser.current_url != case_num_search_url:
        time.sleep(.5)
        browser.get(case_num_search_url)
        if browser.find_elements(By.CLASS_NAME, 'boldred'):
            print('too many requests error')
    # enter case number into search field
    browser.find_element(By.ID, 'displayCaseNumber').send_keys(case_num)
    # perform / click on search
    # time.sleep(.7)
    browser.find_element(By.CLASS_NAME, 'submitBox').click()
    # No result found
    if browser.current_url == "https://eapps.courts.state.va.us/gdcourts/criminalCivilCaseSearch.do":
        return False
    else:
        return True


# scrapes hearing and returns a list of items to be added as row to csv file
def hearing_scrape(case_num):
    row_list = []
    # get case information table
    tables = get_tables(case_num)
    case_information_list = get_table_data('Case Information', tables, case_num)
    # if table not found, take screenshot and exit
    if not case_information_list:
        now = datetime.now().strftime('%d-%m-%y-%H-%M-%S')
        browser.save_screenshot(f'files/logging/err_{now}.png')
        logging.critical(f'Error: Case information not found for case {case_num}')
        print_err(f'Error: Case information not found for case {case_num}')
        exit(1)
    row_list.extend(case_information_list)

    # get plaintiff information table
    plaintiff_information_lists = get_table_data('Plaintiff Information', tables, case_num)
    for plaintiff_list in plaintiff_information_lists:
        row_list.extend(plaintiff_list)
    # add null values for plaintiffs that don't exist up to 6
    for i in range(6 - len(plaintiff_information_lists)):
        for j in range(5):
            row_list.extend(["null"])
    # number of plaintiffs
    row_list.extend([len(plaintiff_information_lists)])

    # get defendant information
    defendant_information_lists = get_table_data('Defendant Information', tables, case_num)

    for defendant_list in defendant_information_lists:
        row_list.extend(defendant_list)
    # add null values for defendants that don't exist up to 6
    for i in range(6 - len(defendant_information_lists)):
        for j in range(5):
            row_list.extend(["null"])
    # number of defendants
    row_list.extend([len(defendant_information_lists)])

    # get hearing information
    # list schema = date, time, result, hearing type, courtroom
    continuances = 0
    no_show_on_first = False
    any_default = False

    hearing_information_lists = get_table_data('Hearing Information', tables, case_num)
    if hearing_information_lists:
        # logic for number of continuances, no show on any court date, and no show on first court date
        if hearing_information_lists[len(hearing_information_lists) - 1][2] == 'Default Judgment':
            no_show_on_first = True
        for hearing_information_list in hearing_information_lists:
            result = hearing_information_list[2]
            if result == 'Continued':
                continuances += 1
            if result == 'Default Judgment':
                any_default = True
        row_list.extend([continuances])
        row_list.extend([no_show_on_first])
        row_list.extend([any_default])
    else:
        row_list.extend(['null', 'null', 'null'])

    # get service/process table
    # service row = person served, process type, date issued, date served, plaintiff, how served
    service_lists = get_table_data('Service/Process', tables, case_num)

    for service_list in service_lists:
        row_list.extend(service_list)
    # add null values for persons served that don't exist up to 6
    for i in range(6 - len(service_lists)):
        for j in range(6):
            row_list.extend(['null'])
    # number of persons served
    row_list.extend([len(service_lists)])
    # get judgement information
    judgment_information_list = get_table_data('Judgment Information', tables, case_num)
    row_list.extend(judgment_information_list)
    # add null values if table is not found
    if not judgment_information_list:
        row_list.extend(['null', 'null', 'null', 'null', 'null', 'null', 'null', 'null', 'null', 'null', 'null', 'null',
                         'null', '', 'null'])
    # get garnishment information
    garnishment_information_list = get_table_data('Garnishment Information', tables, case_num)
    row_list.extend(garnishment_information_list)
    # add null values if table is not found
    if not garnishment_information_list:
        row_list.extend(['null', 'null', 'null', 'null', 'null'])
    # get  appeal information
    appeal_information_list = get_table_data('Appeal Information', tables, case_num)
    row_list.extend(appeal_information_list)
    # add null values if table is not found
    if not appeal_information_list:
        row_list.extend(['null', 'null'])

    return row_list


# headers for csv file
def create_headers():
    headers = ['Case Number',
               'Filed Date',
               'Case Type',
               'Debt Type']

    for i in range(1, 7):
        headers.extend((f'plaintiff {i} name',
                        f'plaintiff {i} dba/ta',
                        f'plaintiff {i} address',
                        f'plaintiff {i} judgment',
                        f'plaintiff {i} attorney'
                        ))
    headers.extend(['number of plaintiffs'])

    for i in range(1, 7):
        headers.extend((f'defendant {i} name',
                        f'defendant {i} dba/ta',
                        f'defendant {i} address',
                        f'defendant {i} judgment',
                        f'defendant {i} attorney'
                        ))
    headers.extend(['number of defendants'])

    headers.extend(('continuances',
                    'no show on first court date',
                    'no show on any court date'))

    for i in range(1, 7):
        headers.extend((f'person served {i} name',
                        f'person served {i} process type',
                        f'person served {i} date issued',
                        f'person served {i} date served',
                        f'person served {i} plaintiff',
                        f'person served {i} how served'
                        ))
    headers.extend(['number of persons served'])

    headers.extend(('Judgement',
                    'Costs',
                    'Attorney Fees',
                    'Principal Amount',
                    'Other Amount',
                    'Interest Award',
                    'Possession',
                    'Writ of Eviction Issue Date',
                    'Writ of Eviction Executed Date',
                    'Homestead Exemption Waived',
                    'Writ of Fieri Facias Issued Date',
                    'Is Judgment Satisfied',
                    'Date Satisfaction Filed',
                    'Other Awarded',
                    'Further Case Information'))

    headers.extend(('garnishee',
                    'address',
                    'garnishee answer',
                    'answer date',
                    'number of checks received'))

    headers.extend(('appeal date',
                    'appealed by'))

    return headers
