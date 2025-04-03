# Apollo Lead Generation Pipeline

A complete pipeline for finding recruiter emails, sending initial emails, and automatically sending follow-up emails on the 3rd and 5th day. The system uses Amazon SES for email delivery and tracks various metrics like bounce rates to help improve the email campaign.

## System Components

1. **Email Scraping**: Scrapes emails from Apollo.io for recruiters without contact information
2. **Email Sending**: Sends initial emails to recruiters
3. **Automated Follow-ups**: Sends follow-up emails on the 3rd and 5th day
4. **Email Tracking**: Monitors delivery, bounces, complaints, and other metrics
5. **Reporting**: Provides statistics on campaign performance

## Setup Instructions

### Prerequisites

- Python 3.8+
- Supabase account and project
- AWS account with SES set up
- Apollo.io account

### Environment Variables

Create a `.env` file with the following variables:

```
SUPABASE_URL=https://your-supabase-url.supabase.co
SUPABASE_KEY=your-supabase-anon-key
AWS_REGION=your-aws-region
AWS_ACCESS_KEY=your-aws-access-key
AWS_SECRET_KEY=your-aws-secret-key
SENDER_EMAIL=your-verified-sender-email
SENDER_NAME=Your Name
APOLLO_USERNAME=your-apollo-username
APOLLO_PASSWORD=your-apollo-password
```
