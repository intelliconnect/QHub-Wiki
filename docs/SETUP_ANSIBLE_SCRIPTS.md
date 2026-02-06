[← Previous: GitHub Config](GITHUB_CONFIG.md) | [Next: WikiJS Configuration →](WIKIJS.md)


# STEP 1: INSTALL ANSIBLIE 
```
# update pakages
sudo apt update

# add official ansible repositoy
sudo apt-add-repository ppa:ansible/ansible

# again update the pakages
sudo apt update
 
# install ansible
sudo apt install ansible
 
# check installation
ansible --version 
```

# STEP 2: CLONE QHUB WIKI REPOSITORY
```
git clone https://github.com/intelliconnect/QHub-Wiki
```

# STEP 3: 
Open vars/secrets.yaml and update the required keys
```
# If you don't have semaphoreui for the implementation of secrets, you can manually place the screts in this file. 
# env.j2 & Ansible Playbook.yaml Docker-compose.yaml will pick the secrets from here.

# Place All the Secrets in this file


# ANTHROPIC_API_KEY = Get from Developer.
ANTHROPIC_API_KEY: ""

# GROQ_API_KEY = Get from Developer.
GROQ_API_KEY: ""


# INGEST_API_SECRET = Create Secrets.
INGEST_API_SECRET: ""



# KB_GIT_BRANCH = Knowledge-Base Repository Branch.
KB_GIT_BRANCH: "main"

# KB_GIT_COMMIT_EMAIL = To put email inside Commit Message (can be admin).
KB_GIT_COMMIT_EMAIL: ""

# KB_GIT_COMMIT_NAME = To put name inside Commit Message (can be admin).
KB_GIT_COMMIT_NAME: ""



# KB_REPO_GITHUB_TOKEN = To Clone Knowledge-Base Repository and update the Github Actions Pipeline.
KB_REPO_GITHUB_TOKEN: ""

# KB_REPO_HTTP_URL = HTTPS GitHub URL for Ansible Clone to the Repo.
KB_REPO_HTTP_URL: ""

# KB_REPO_OWNER = Owner name of the Knowledge-Base Repository
KB_REPO_OWNER: ""

# KB_REPO_NAME = Name of the Knowledge-Base Repository
KB_REPO_NAME: ""

# KB_REPO_SSH_URL = Github SSH URL
KB_REPO_SSH_URL: ""


# QDRANT_API_KEY = Create Random Key
QDRANT_API_KEY: ""

# QDRANT_COLLECTION_NAME = Qdrant Collection Name
QDRANT_COLLECTION_NAME: ""



# WikiJS Admin Configuration
WIKIJS_ADMIN_EMAIL: ""
WIKIJS_ADMIN_PASSWORD: ""

# WIKI_DOMAIN = Used for creating NGINX config.
# Setup DOC-EMBEDDINGS-QDRANT & QDRANT.
WIKI_DOMAIN: ""
```


# STEP 4: RUN ANSIBLE PLAYBOOK
```
# command to run the Playbook with vars file provided with secrets.
ansible-playbook qhub-wiki-deploy.yml --extra-vars /vars/secret.yaml # secret file
```

Ansible script will setup/provision on your server
1. [WikiJS](https://github.com/requarks/wiki)
2. [Qdrant Vector DB](https://github.com/qdrant/qdrant)
3. QHub Wiki Custom API ([Python FastAPI](https://fastapi.tiangolo.com/))
4. [NGINX](https://github.com/nginx/nginx)
5. [Certbot SSL](https://certbot.eff.org/)



# STEP 5: VERIFY
[← Previous: GitHub Config](GITHUB_CONFIG.md) | [Next: WikiJS Configuration →](WIKIJS.md)