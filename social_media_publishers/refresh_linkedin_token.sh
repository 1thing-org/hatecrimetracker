#
# Get secrete from Google Cloud Console
# {
#    "client_id": ,
#    "client_secret": ,
#   "access_token" : ,
#    "refresh_token": ,
#    "redirect_uri": "http://localhost:8080/callback",
#    "company_id": 
#}

# Set the following variabales and run the script
REFRESH_TOKEN=
URL=https://www.linkedin.com/oauth/v2/accessToken
CLIENT_SECRET=
CLIENT_ID=
curl -X POST $URL -d "grant_type=refresh_token&refresh_token=$REFRESH_TOKEN&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET" \
-H 'Content-Type: application/x-www-form-urlencoded'

echo "Make sure to set the new token in the secret."
