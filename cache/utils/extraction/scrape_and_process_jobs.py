import time
import traceback

from selenium.common.exceptions import StaleElementReferenceException

from ..navigation.scroll_to_parent_ui import scroll_to_parent_ul
from .process_job_data import process_job_data
from ..navigation.interact_with_apollo import interact_with_apollo


async def scrape_and_process_jobs(driver, start_url, max_items=100, supabase=None):
    """Scrape and process jobs from LinkedIn search results"""
    item_count = 0

    try:
        while item_count < max_items:
            url = f"{start_url}&start={item_count}"
            driver.get(url)
            time.sleep(2)

            try:
                # Find job listings
                list_items = scroll_to_parent_ul(driver, "job-card-container")
                if not list_items or len(list_items) == 0:
                    print("No job listings found on page")
                    break

                print(f"Found {len(list_items)} job listings on current page")

                # Process each job listing
                for index, item in enumerate(list_items):
                    for attempt in range(3):
                        try:
                            # Click on job listing to view details
                            item.click()
                            time.sleep(2)

                            # Extract job ID
                            job_id = item.get_attribute("data-job-id")
                            print(f"Processing job ID: {job_id}")

                            # Process job data
                            (
                                hiring_manager_name,
                                hiring_manager_linkedin_url,
                                company_domain,
                            ) = await process_job_data(driver, job_id, supabase)

                            # Interact with Apollo if hiring manager info is available
                            if hiring_manager_name and hiring_manager_linkedin_url:
                                print(
                                    f"Found hiring manager: {hiring_manager_name}, attempting to add to Apollo sequence"
                                )
                                success = interact_with_apollo(
                                    driver, hiring_manager_linkedin_url
                                )
                                if success:
                                    print(
                                        f"Successfully added {hiring_manager_name} to Apollo sequence"
                                    )
                                else:
                                    print(
                                        f"Failed to add {hiring_manager_name} to Apollo sequence"
                                    )

                            break  # Break out of retry loop if successful

                        except StaleElementReferenceException:
                            if attempt == 2:  # Last attempt
                                print(f"Failed to process job after 3 attempts")
                            else:
                                print(
                                    f"StaleElementReferenceException occurred, retrying (attempt {attempt + 1})"
                                )
                                time.sleep(1)
                        except Exception as e:
                            print(f"Error processing job listing: {str(e)}")
                            break

                # Move to next page of results
                print(f"Processed {len(list_items)} job listings, moving to next page")
                item_count += 25

            except Exception as page_error:
                print(f"Error processing page: {str(page_error)}")
                item_count += 25  # Move to next page despite error

    except Exception as e:
        print(f"Error in scrape_and_process_jobs: {str(e)}")
        traceback.print_exc()
