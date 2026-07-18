import os
import git
import datetime

def get_repo():
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return git.Repo(repo_path)

def commit_and_push(message="Auto-commit"):
    try:
        repo = get_repo()
        
        # Check if there are changes
        if not repo.is_dirty(untracked_files=True):
            print("No changes to commit.")
            return True
            
        repo.git.add(A=True)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        full_message = f"{message} {timestamp}"
        repo.index.commit(full_message)
        print(f"Committed: {full_message}")

        # Push to remote using token
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("ERROR: GITHUB_TOKEN not found in environment.")
            return False

        # Get remote URL and inject token
        remote = repo.remote(name='origin')
        original_url = next(remote.urls)
        
        # Parse original URL to inject token
        if "github.com" in original_url:
            if original_url.startswith("https://"):
                base_url = original_url.split("https://")[1]
                # Remove any existing credentials
                if "@" in base_url:
                    base_url = base_url.split("@")[1]
                push_url = f"https://{token}@{base_url}"
                print(f"Pushing to {base_url}...")
                
                # Use a custom environment to avoid prompting
                custom_env = os.environ.copy()
                custom_env["GIT_ASKPASS"] = "echo" 
                
                repo.git.push(push_url, 'main', env=custom_env)
                print("Push successful.")
                return True
            else:
                print("ERROR: Remote is not HTTPS.")
                return False
        else:
            print("ERROR: Remote is not github.com.")
            return False

    except Exception as e:
        print(f"ERROR during commit and push: {e}")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    success = commit_and_push("Auto-save")
    if success:
        print("Test push succeeded!")
    else:
        print("Test push failed.")
