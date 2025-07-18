from supabase import Client, create_client


async def insert_data(
    supabase: Client,
    company_name,
    company_location,
    company_url,
    title,
    role_meta,
    hiring_manager_name,
    hiring_manager_linkedin_url,
    job_details,
    job_id,
    company_domain,
    company_details,
):
    """Insert job and company data into Supabase"""
    try:
        company_url = company_url.replace("/about", "").replace("/life", "")
        company_response = (
            supabase.table("companies")
            .select("id")
            .eq("linkedin_url", company_url)
            .execute()
        )
        company_id = company_response.data[0]["id"] if company_response.data else None

        if not company_id and company_domain:
            domain_response = (
                supabase.table("companies")
                .select("id")
                .eq("company_domain", company_domain)
                .execute()
            )
            company_id = domain_response.data[0]["id"] if domain_response.data else None

        if not company_id:
            company_response = (
                supabase.table("companies")
                .insert(
                    {
                        "name": company_name,
                        "linkedin_url": company_url,
                        "location": company_location,
                        "company_domain": company_domain,
                        "metadata": company_details,
                    }
                )
                .execute()
            )
            company_id = company_response.data[0]["id"]
        else:
            update_data = {}
            if company_domain:
                update_data["company_domain"] = company_domain
            if company_details and company_details != "{}":
                update_data["metadata"] = company_details
            if update_data:
                supabase.table("companies").update(update_data).eq(
                    "id", company_id
                ).execute()

        recruiter_id = None
        if hiring_manager_name and hiring_manager_linkedin_url:
            try:
                recruiter_response = (
                    supabase.table("recruiters")
                    .select("id")
                    .eq("linkedin_url", hiring_manager_linkedin_url)
                    .execute()
                )
                if recruiter_response.data:
                    recruiter_id = recruiter_response.data[0]["id"]
                    supabase.table("recruiters").update(
                        {"name": hiring_manager_name, "company_domain": company_domain}
                    ).eq("id", recruiter_id).execute()
                else:
                    recruiter_response = (
                        supabase.table("recruiters")
                        .insert(
                            {
                                "name": hiring_manager_name,
                                "linkedin_url": hiring_manager_linkedin_url,
                                "company_domain": company_domain,
                            }
                        )
                        .execute()
                    )
                    recruiter_id = recruiter_response.data[0]["id"]
            except Exception as e:
                print(f"Error handling recruiter: {str(e)}")
                try:
                    recruiter_response = (
                        supabase.table("recruiters")
                        .select("id")
                        .eq("linkedin_url", hiring_manager_linkedin_url)
                        .execute()
                    )
                    if recruiter_response.data:
                        recruiter_id = recruiter_response.data[0]["id"]
                except:
                    pass

        # Insert job data
        job_data = {
            "company_id": company_id,
            "title": title,
            "description": job_details,
            "role_metadata": role_meta,
            "id": int(job_id),
        }

        if recruiter_id:
            job_data["recruiter_id"] = recruiter_id

        supabase.table("linkedin_jobs").insert(job_data).execute()

        return True
    except Exception as e:
        print(f"Error inserting data: {str(e)}")
        return False
