# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "simple-term-menu",
# ]
# ///

import sys
import os
import subprocess
from pathlib import Path
from simple_term_menu import TerminalMenu


def run_command(cmd, cwd=None, check=True, input=None):
    """Run a shell command and return the result."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, input=input
    )
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result


def get_git_root():
    """Get the root directory of the current git repository."""
    result = run_command("git rev-parse --show-toplevel")
    return result.stdout.strip()


def get_worktree_path(branch_name):
    """Check if a worktree exists for the given branch and return its path."""
    result = run_command("git worktree list --porcelain")
    lines = result.stdout.strip().split("\n")

    current_worktree = None
    for line in lines:
        if line.startswith("worktree "):
            current_worktree = line.split(" ", 1)[1]
        elif line.startswith("branch ") and current_worktree:
            branch = line.split(" ", 1)[1]
            if branch == f"refs/heads/{branch_name}":
                return current_worktree
            current_worktree = None

    return None


def get_all_worktrees():
    """Get all worktrees with their branch names."""
    result = run_command("git worktree list --porcelain")
    lines = result.stdout.strip().split("\n")

    worktrees = []
    current_worktree = None
    current_path = None

    for line in lines:
        if line.startswith("worktree "):
            current_path = line.split(" ", 1)[1]
        elif line.startswith("branch ") and current_path:
            branch = line.split(" ", 1)[1]
            if branch.startswith("refs/heads/"):
                branch_name = branch.replace("refs/heads/", "")
                # Skip the main worktree (git root)
                git_root = get_git_root()
                if current_path != git_root:
                    worktrees.append((branch_name, current_path))
            current_path = None

    return worktrees


def branch_exists(branch_name):
    """Check if a branch exists."""
    result = run_command(
        f"git show-ref --verify --quiet refs/heads/{branch_name}", check=False
    )
    return result.returncode == 0


def main():
    if len(sys.argv) < 2:
        print("Usage: claudebg <command> [args]")
        print("Commands:")
        print("  create <branch-name>   Create and switch to a git worktree")
        print("  destroy [branch-name] [--force]  Remove worktree and delete branch")
        print(
            "                                   (interactive mode if no branch name given)"
        )
        print(
            "                                   --force: skip merge check and force delete"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) != 3:
            print("Usage: claudebg create <branch-name>")
            sys.exit(1)
        branch_name = sys.argv[2]
        create_worktree(branch_name)
    elif command == "destroy":
        force = False
        branch_name = None

        # Parse arguments
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--force":
                force = True
            else:
                if branch_name is None:
                    branch_name = args[i]
                else:
                    print("Error: Too many arguments")
                    print("Usage: claudebg destroy [branch-name] [--force]")
                    sys.exit(1)
            i += 1

        if branch_name is None:
            # Interactive mode
            destroy_worktree_interactive(force=force)
        else:
            # Direct mode with branch name
            destroy_worktree(branch_name, force=force)
    else:
        print(f"Unknown command: {command}")
        print("Usage: claudebg <command> [args]")
        print("Commands:")
        print("  create <branch-name>   Create and switch to a git worktree")
        print("  destroy [branch-name] [--force]  Remove worktree and delete branch")
        print(
            "                                   (interactive mode if no branch name given)"
        )
        print(
            "                                   --force: skip merge check and force delete"
        )
        sys.exit(1)


def create_worktree(branch_name):
    # Get current directory and git root
    current_dir = os.getcwd()
    git_root = get_git_root()

    # Get the current branch to store as parent
    parent_branch = get_current_branch()

    # Calculate relative path from git root to current directory
    relative_path = os.path.relpath(current_dir, git_root)
    if relative_path == ".":
        relative_path = ""

    # Check if worktree already exists
    worktree_path = get_worktree_path(branch_name)

    if worktree_path:
        # Worktree already exists, prompt the user
        print(f"Worktree '{branch_name}' already exists.")
        response = input("Would you like to attach instead? (y/n): ").strip().lower()

        if response != 'y':
            print("Operation cancelled.")
            sys.exit(0)
    else:
        # Create branch if it doesn't exist
        if not branch_exists(branch_name):
            print(f"Creating new branch: {branch_name} from {parent_branch}")
            run_command(f"git checkout -b {branch_name}")
            # Store the parent branch in the description
            set_branch_parent(branch_name, parent_branch)
            run_command("git checkout -")  # Switch back to original branch

        # Create worktree as sibling directory
        parent_dir = os.path.dirname(git_root)
        repo_name = os.path.basename(git_root)
        worktree_dir = os.path.join(parent_dir, f"{repo_name}-{branch_name}")

        print(f"Creating new worktree at: {worktree_dir}")
        run_command(f"git worktree add '{worktree_dir}' '{branch_name}'")
        worktree_path = worktree_dir

    # Navigate to the worktree directory (and subdirectory if needed)
    target_dir = worktree_path
    if relative_path:
        target_dir = os.path.join(worktree_path, relative_path)
        # Create subdirectory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

    # Change to the target directory and run zellij
    os.chdir(target_dir)
    print(f"Launching zellij in: {target_dir}")
    os.execvp("zellij", ["zellij", "--layout", "claude"])


def get_current_branch():
    """Get the current branch name."""
    result = run_command("git rev-parse --abbrev-ref HEAD")
    return result.stdout.strip()


def set_branch_parent(branch_name, parent_branch):
    """Set the parent branch in the branch description."""
    description = f"Parent branch: {parent_branch}"
    run_command(f"git config branch.{branch_name}.description '{description}'")


def get_branch_parent(branch_name):
    """Get the parent branch from the branch description."""
    result = run_command(f"git config branch.{branch_name}.description", check=False)
    if result.returncode == 0 and result.stdout.strip():
        description = result.stdout.strip()
        if description.startswith("Parent branch: "):
            return description.replace("Parent branch: ", "").strip()
    return None


def get_main_branch():
    """Try to determine the main branch (main, master, or develop)."""
    for branch in ["main", "master", "develop"]:
        if branch_exists(branch):
            return branch
    # If none of the common main branches exist, use the first branch
    result = run_command("git branch -r | grep -v HEAD | head -1")
    if result.stdout.strip():
        return result.stdout.strip().split("/")[-1]
    return None


def is_branch_merged(branch_name, target_branch):
    """Check if branch_name has been merged into target_branch."""
    # Get the worktree path for the branch
    worktree_path = get_worktree_path(branch_name)

    # Run the command from within the worktree directory
    result = run_command(
        f"git branch --merged {target_branch}", check=False, cwd=worktree_path
    )
    merged_branches = result.stdout.strip().split("\n")
    return any(
        branch.strip().strip("*").strip() == branch_name for branch in merged_branches
    )


def has_remote_branch(branch_name):
    """Check if a remote branch exists."""
    result = run_command(f"git ls-remote --heads origin {branch_name}", check=False)
    return bool(result.stdout.strip())


def destroy_worktree_interactive(force=False):
    """Interactive mode for destroying worktrees."""
    # Get all worktrees
    worktrees = get_all_worktrees()

    if not worktrees:
        print("No worktrees found to destroy.")
        return

    # Create menu options
    menu_options = []
    for branch_name, path in worktrees:
        menu_options.append(branch_name)

    # Add cancel option
    menu_options.append("Cancel")

    # Show interactive menu
    terminal_menu = TerminalMenu(menu_options, title="Select a worktree to destroy:")
    menu_entry_index = terminal_menu.show()

    # Handle selection
    if menu_entry_index is None or menu_entry_index == len(menu_options) - 1:
        print("Cancelled.")
        return

    # Get selected branch name
    selected_branch = worktrees[menu_entry_index][0]

    # Confirm destruction
    print(f"\nSelected: {selected_branch}")
    confirm_menu = TerminalMenu(
        ["Yes, destroy it", "No, cancel"],
        title=f"Are you sure you want to destroy the worktree for '{selected_branch}'?",
    )
    confirm_index = confirm_menu.show()

    if confirm_index == 0:
        destroy_worktree(selected_branch, force=force)
    else:
        print("Cancelled.")


def destroy_worktree(branch_name, force=False):
    # Check if worktree exists
    worktree_path = get_worktree_path(branch_name)
    if not worktree_path:
        print(f"Error: No worktree found for branch '{branch_name}'")
        sys.exit(1)

    # Get the parent branch from the description
    parent_branch = get_branch_parent(branch_name)

    # If no parent branch is stored, fall back to main branch detection
    if not parent_branch:
        print(f"Warning: No parent branch information found for '{branch_name}'")
        parent_branch = get_main_branch()
        if not parent_branch:
            print("Error: Could not determine the parent branch")
            print(
                "Please specify the parent branch or merge manually before destroying"
            )
            sys.exit(1)
        print(f"Using '{parent_branch}' as the parent branch")

    if not force:
        print(f"Checking if '{branch_name}' has been merged into '{parent_branch}'...")

        # Check if the branch has been merged
        if not is_branch_merged(branch_name, parent_branch):
            print(f"Error: Branch '{branch_name}' contains unmerged changes.")
            print(
                f"Please merge the changes into '{parent_branch}' before destroying the worktree."
            )
            print(f"Or use --force to delete anyway.")
            sys.exit(1)
    else:
        print(f"Force flag enabled, skipping merge check...")

    # Remove the worktree
    print(f"Removing worktree at: {worktree_path}")
    run_command(f"git worktree remove --force '{worktree_path}'")

    # Delete the local branch
    print(f"Deleting local branch: {branch_name}")
    if force:
        run_command(f"git branch -D {branch_name}")
    else:
        run_command(f"git branch -d {branch_name}")

    # Delete the remote branch if it exists
    if has_remote_branch(branch_name):
        print(f"Deleting remote branch: origin/{branch_name}")
        run_command(f"git push origin --delete {branch_name}")

    print(f"Successfully destroyed worktree and branch '{branch_name}'")


if __name__ == "__main__":
    main()
