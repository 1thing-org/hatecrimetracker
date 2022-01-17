import requests
 
from ln_oauth import auth, headers
 
credentials = 'linkedin_credentials.json'
access_token = auth(credentials) # Authenticate the API
headers = headers(access_token) # Make the headers to attach to the API call.
 
def user_info(headers):
    '''
    Get user information from Linkedin
    '''
    response = requests.get('https://api.linkedin.com/v2/me', headers = headers)
    user_info = response.json()
    return user_info
 
# Get user id to make a UGC post
user_info = user_info(headers)
urn = user_info['id']
 
# UGC will replace shares over time.
api_url = 'https://api.linkedin.com/v2/ugcPosts'
# author = f'urn:li:person:{urn}'
author = "urn:li:organization:78324103" # 2278324103"
 
message = '''
Even though the anti-Asian hate is not under the spotlight in today’s news, 
the issue still exists. The AAPI community and our allies could sit still 
doing nothing today, waiting until another horrible incident will inevitably 
happen again. Or we could continue the momentum that we all built together 
in the past few months. We shall continue contributing to the cause, one 
small thing at a time. Together, we can eventually gain the racial equality we deserve.

#StopAAPIHate #1ThingAgainstRacism
'''

link = 'https://hatecrimetracker.1thing.org/'
link_text = 'Anti-Asian Hate Crime Tracker'
link_message = "We're working on a new website to track anti-Asian hate crimes. Check it out!"
 
post_data = {
    "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": message
                },
                "shareMediaCategory": "ARTICLE",
                "media": [
                    {
                        "status": "READY",
                        "description": {
                            "text": link_message
                        },
                        "originalUrl": link,
                        "title": {
                            "text": link_text
                        }
                    }
                ]
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
 
if __name__ == '__main__':
    r = requests.post(api_url, headers=headers, json=post_data)

    print("Article posted:", r.json())