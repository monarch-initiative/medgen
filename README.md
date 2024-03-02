# MedGen ingest

## Prerequisites
On macOS, (2) and (3) should be available without the need for installation.
1. Python 3.9+
2. `make`
3. Perl
4. Docker
5. Docker images  
  One or both of the following, depending on if you want to run the stable build `latest` or `dev`:
    - a. `docker pull obolibrary/odkfull:latest`
    - b. `docker pull obolibrary/odkfull:dev` 

## Setup
1. Give permission to run Perl: `chmod +x ./bin/*.pl`
2. Install Python dependencies: `pip install -r requirements.txt`

## Running
`sh run.sh make all`
