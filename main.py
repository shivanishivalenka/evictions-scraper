from datetime import timedelta
from functions import *
import csv
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# for logging
start_time = datetime.now()
case_count = 0
total_case_count = 0
page_count = 0

hearing_date_search_url = 'https://eapps.courts.state.va.us/gdcourts/caseSearch.do?fromSidebar=true&searchLanding' \
                          '=searchLanding&searchType=hearingDate&searchDivision=V&searchFipsCode=510&curentFipsCode=510'

# Accept terms
browser.get('https://eapps.courts.state.va.us/gdcourts')
time.sleep(3)
browser.find_element(By.XPATH, '/html/body/table/tbody/tr[1]/td/table/tbody/tr[2]/td/div[2]/main/form/table/tbody/tr[2]/td/input[1]').click()
time.sleep(3)
# get date
cleaned_today = datetime.today().strftime('%m-%d-%Y')
# write headers for case output file
with open(f'files/hearings_scraped_on_{cleaned_today}.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(create_headers())

# date range - number of days backwards, and number of days forwards
date_range = 70
start_date = datetime.today() - timedelta(date_range)
date_list = [start_date + timedelta(days=x) for x in range(date_range * 2)]

# rows list for summary page
rows_to_write = []

# open hearing scrape file to write to
with open(f'files/hearings_scraped_on_{cleaned_today}.csv', 'a', newline='') as file:
    writer = csv.writer(file)
    # for each date
    for date in date_list:
        # format date
        cleaned_date = date.strftime('%m/%d/%Y')
        while browser.current_url != hearing_date_search_url:
            time.sleep(.5)
            browser.get(hearing_date_search_url)
        # enter date and search
        browser.find_element(By.ID, 'txthearingdate').send_keys(cleaned_date)
        time.sleep(.5)
        browser.find_element(By.NAME, 'caseSearch').click()
        # print searched date
        print(f'{cleaned_date}: ')
        # reset case count
        case_count = 0
        # ===CHANGED: STEP 1 - collect all UD case numbers across ALL pages first===
        # previously this was mixed with processing which caused stale element crash
        # now we collect everything into plain strings before touching any case
        ud_cases = []
 
        while True:
            time.sleep(2)  # wait for page to fully load
            try:
                rows = browser.find_elements(By.CSS_SELECTOR, 'tr.evenRow, tr.oddRow')
                for row in rows:
                    try:
                        tds = row.find_elements(By.CSS_SELECTOR, "td.gridrow")
                        if len(tds) > 4 and tds[4].text == "Unlawful Detainer":
                            # extract to plain strings immediately
                            td_list = [td.text for td in tds[1:]]
                            td_list.append(cleaned_date)
                            rows_to_write.append(td_list)
                            ud_cases.append(tds[1].text)  # plain string, not element
                    except Exception as e:
                        logging.warning(f'Stale row skipped on {cleaned_date}: {e}')
                        continue
            except Exception as e:
                logging.warning(f'Could not get rows for {cleaned_date}: {e}')
 
            # ===NEW: pagination - click Next if it exists, else stop===
            try:
                next_button = browser.find_element(By.LINK_TEXT, 'Next')
                next_button.click()
            except:
                break  # no more pages, move on
 
        # ===CHANGED: STEP 2 - now process each case number separately===
        # using plain string case numbers, no element references from step 1
        # navigating to case number search page fresh for each case
        for case_num in ud_cases:
            try:
                browser.get(case_num_search_url)
                time.sleep(1)
                browser.find_element(By.ID, 'displayCaseNumber').send_keys(case_num)
                browser.find_element(By.CLASS_NAME, 'submitBox').click()
                time.sleep(1)
                writer.writerow(hearing_scrape(case_num))
                case_count += 1
                total_case_count += 1
                print(f'    Scraped case: {case_num}')
            except Exception as e:
                logging.warning(f'Failed to scrape case {case_num}: {e}')
                continue
 
        page_count += 1
        runtime_delta = str(datetime.now() - start_time)
        runtime = runtime_delta.split('.')[0]
        logging.info(f'page:{page_count} date:{cleaned_date} cases scraped:{case_count} total:{total_case_count} runtime:{runtime}')
        print(f'    Cases scraped on page: {case_count}')
        print(f'    Total cases scraped: {total_case_count}')
        print(f'    Pages scraped: {page_count} / {date_range * 2}')
        print(f'    Runtime: {runtime}')

# write to summary scrape output file
with open(f'files/summary_scrape_on_{cleaned_today}', 'w', newline='') as summary:
    writer = csv.writer(summary)
    headers = ['case_number', 'defendant', 'plaintiff', 'case type', 'hearing time', 'date']
    writer.writerow(headers)
    writer.writerows(rows_to_write)

# print/log total runtime
print(f'Scraped {total_case_count} cases from {page_count} pages in {runtime}')
logging.info(f'Scraped {total_case_count} cases from {page_count} pages in {runtime}')
