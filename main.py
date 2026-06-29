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
        case_nums = []
        # get rows of cases
        rows = browser.find_elements(By.CSS_SELECTOR, 'tr.evenRow, tr.oddRow')
        for row in rows:
            td_list = []
            # get table data cells of each row
            tds = row.find_elements(By.CSS_SELECTOR, "td.gridrow")
            # check if case is unlawful detainer
            if tds[4].text == "Unlawful Detainer":
                # splice to remove checkbox
                for td in tds[1:]:
                    td_list.append(td.text)
                td_list.append(cleaned_date)
                rows_to_write.append(td_list)
                case_nums.append(tds[1].text)
                # open link in new tab
                link = tds[1].find_element(By.CSS_SELECTOR, "a")
                case_num = link.text
                # time.sleep(1)
                ActionChains(browser) \
                    .key_down(Keys.CONTROL) \
                    .click(link) \
                    .key_up(Keys.CONTROL) \
                    .perform()
                # switch to new tab
                browser.switch_to.window(browser.window_handles[1])
                # scrape page and write row to file
                writer.writerow(hearing_scrape(case_num))
                case_count += 1
                total_case_count += 1
                print(f'    Scraped case: {case_num}')
                # close tab
                browser.close()
                # switch to first tab
                browser.switch_to.window(browser.window_handles[0])
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
