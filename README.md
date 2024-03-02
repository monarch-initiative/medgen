# MedGen ingest

## Prerequisites 
On macOS, Perl should be available without the need for installation.
Python and Perl are also dev dependencies. They're not needed to run the docker containers, but they are needed for 
local development situations / debugging.
1. Python 3.9+
2. Perl
3. Docker
4. Docker images  
  One or both of the following, depending on if you want to run the stable build `latest` or `dev`:
    - a. `docker pull obolibrary/odkfull:latest`
    - b. `docker pull obolibrary/odkfull:dev` 

## Setup
1. Give permission to run Perl: `chmod +x ./bin/*.pl`
2. Install Python dependencies: `pip install -r requirements.txt`

## Running
`sh run.sh make all`
