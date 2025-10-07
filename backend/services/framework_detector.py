import subprocess
import tempfile
import os
import shutil
from typing import Optional, Tuple, List, Set
import json
import re


class FrameworkDetector:
    """Service for detecting agent frameworks from GitHub repositories."""
    
    @staticmethod
    def clone_repo(repo_url: str, branch: str = "main") -> str:
        """
        Clone a GitHub repository to a temporary directory.
        
        Args:
            repo_url: GitHub repository URL
            branch: Branch name to clone
            
        Returns:
            Path to the cloned repository
            
        Raises:
            Exception: If clone fails
        """
        temp_dir = tempfile.mkdtemp(prefix="agent_")
        
        try:
            result = subprocess.run(
                ["git", "-c", "credential.helper=", "clone", "--depth", "1", "--branch", branch, repo_url, temp_dir],
                check=True,
                capture_output=True,
                text=True,
                timeout=600  # 600 second timeout
            )
            return temp_dir
        except subprocess.CalledProcessError as e:
            # Cleanup on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            error_msg = e.stderr if e.stderr else str(e)
            raise Exception(f"Failed to clone repository: {error_msg}")
        except subprocess.TimeoutExpired:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise Exception("Repository clone timed out after 600 seconds")
    
    @staticmethod
    def detect_framework(repo_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect the agent framework used in the repository.
        
        Args:
            repo_path: Path to the cloned repository
            
        Returns:
            Tuple of (framework_name, commit_hash)
        """
        framework = None
        commit_hash = None
        
        # Get commit hash
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            commit_hash = result.stdout.strip()
        except subprocess.CalledProcessError:
            pass
        
        # Aggregate evidence from multiple sources
        try:
            framework = (
                FrameworkDetector._detect_from_requirements(repo_path)
                or FrameworkDetector._detect_from_pyproject(repo_path)
                or FrameworkDetector._detect_from_pipfile(repo_path)
                or FrameworkDetector._detect_from_lockfiles(repo_path)
                or FrameworkDetector._detect_from_imports(repo_path)
                or "unknown"
            )
        except Exception as e:
            print(f"Framework detection error: {e}")
            framework = "unknown"

        return framework, commit_hash

    @staticmethod
    def _detect_from_requirements(repo_path: str) -> Optional[str]:
        req_file = os.path.join(repo_path, "requirements.txt")
        if not os.path.exists(req_file):
            return None
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                text = f.read().lower()
            return FrameworkDetector._classify_by_keywords(text)
        except Exception as e:
            print(f"Error reading requirements.txt: {e}")
            return None

    @staticmethod
    def _detect_from_pyproject(repo_path: str) -> Optional[str]:
        pyproject = os.path.join(repo_path, "pyproject.toml")
        if not os.path.exists(pyproject):
            return None
        try:
            # Minimal TOML read to avoid extra deps
            with open(pyproject, "r", encoding="utf-8") as f:
                text = f.read().lower()
            return FrameworkDetector._classify_by_keywords(text)
        except Exception as e:
            print(f"Error reading pyproject.toml: {e}")
            return None

    @staticmethod
    def _detect_from_pipfile(repo_path: str) -> Optional[str]:
        pipfile = os.path.join(repo_path, "Pipfile")
        if not os.path.exists(pipfile):
            return None
        try:
            with open(pipfile, "r", encoding="utf-8") as f:
                text = f.read().lower()
            return FrameworkDetector._classify_by_keywords(text)
        except Exception as e:
            print(f"Error reading Pipfile: {e}")
            return None

    @staticmethod
    def _detect_from_lockfiles(repo_path: str) -> Optional[str]:
        candidates = [
            os.path.join(repo_path, "poetry.lock"),
            os.path.join(repo_path, "uv.lock"),
            os.path.join(repo_path, "Pipfile.lock"),
        ]
        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read().lower()
                # Pipfile.lock is JSON; best-effort read keywords from either raw text or parsed JSON
                if path.endswith("Pipfile.lock"):
                    try:
                        data = json.loads(text)
                        text = json.dumps(data).lower()
                    except Exception:
                        pass
                classified = FrameworkDetector._classify_by_keywords(text)
                if classified:
                    return classified
            except Exception as e:
                print(f"Error reading lockfile {os.path.basename(path)}: {e}")
        return None

    @staticmethod
    def _detect_from_imports(repo_path: str) -> Optional[str]:
        # Walk a limited set of files to infer from imports
        ignore_dirs: Set[str] = {".git", "venv", ".venv", "env", ".env", "node_modules", "__pycache__"}
        max_files = 500
        scanned = 0
        patterns = {
            "langgraph": re.compile(r"^\s*(from|import)\s+langgraph(\.|\s|$)") ,
            "langchain": re.compile(r"^\s*(from|import)\s+langchain(\.|\s|$)"),
            "crewai": re.compile(r"^\s*(from|import)\s+crewai(\.|\s|$)"),
            "autogpt": re.compile(r"^\s*(from|import)\s+autogpt(\.|\s|$)"),
        }
        # Priority order: langgraph > langchain > crewai > autogpt
        priority: List[str] = ["langgraph", "langchain", "crewai", "autogpt"]
        found: Set[str] = set()
        try:
            for root, dirs, files in os.walk(repo_path):
                # In-place prune ignored dirs
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                for file in files:
                    if not file.endswith(".py"):
                        continue
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            for i in range(200):  # only first 200 lines per file
                                line = f.readline()
                                if not line:
                                    break
                                for key, regex in patterns.items():
                                    if regex.search(line):
                                        found.add(key)
                    except Exception:
                        pass
                    scanned += 1
                    if scanned >= max_files:
                        raise StopIteration
        except StopIteration:
            pass

        for key in priority:
            if key in found:
                return key
        return None

    @staticmethod
    def _classify_by_keywords(text: str) -> Optional[str]:
        text = text or ""
        # Priority order matters
        if "langgraph" in text:
            return "langgraph"
        if "langchain" in text:
            return "langchain"
        if "crewai" in text:
            return "crewai"
        if "autogpt" in text:
            return "autogpt"
        # If dependencies exist but none matched, return custom to distinguish from unknown
        if any(k in text for k in ["project", "tool.poetry", "requires", "dependencies", "package"]):
            return "custom"
        return None
    
    @staticmethod
    def cleanup(repo_path: str):
        """
        Remove the cloned repository directory.
        
        Args:
            repo_path: Path to the repository to remove
        """
        try:
            shutil.rmtree(repo_path, ignore_errors=True)
        except Exception as e:
            print(f"Warning: Failed to cleanup {repo_path}: {e}")
    
    @staticmethod
    def validate_repo_url(repo_url: str) -> bool:
        """
        Basic validation of GitHub repository URL.
        
        Args:
            repo_url: Repository URL to validate
            
        Returns:
            True if URL appears valid, False otherwise
        """
        if not repo_url:
            return False
        
        # Check for common GitHub URL patterns
        valid_patterns = [
            "github.com/",
            "https://github.com/",
            "git@github.com:"
        ]
        
        return any(pattern in repo_url for pattern in valid_patterns)