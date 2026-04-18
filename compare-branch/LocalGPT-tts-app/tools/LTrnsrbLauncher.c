#include <errno.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

static void show_alert(const char *message) {
    pid_t pid = 0;
    char script[2048];
    size_t j = 0;

    j += (size_t)snprintf(script + j, sizeof(script) - j, "display alert \"LTrnsrb\" message \"");
    for (size_t i = 0; message[i] != '\0' && j + 2 < sizeof(script); i++) {
        if (message[i] == '"' || message[i] == '\\') {
            script[j++] = '\\';
        }
        script[j++] = message[i];
    }
    if (j + 2 < sizeof(script)) {
        script[j++] = '"';
        script[j] = '\0';
    }

    char *const argv[] = {"/usr/bin/osascript", "-e", script, NULL};
    if (posix_spawn(&pid, "/usr/bin/osascript", NULL, NULL, argv, environ) == 0) {
        waitpid(pid, NULL, 0);
    }
}

static int path_dirname(char *path) {
    char *dir = dirname(path);
    if (!dir) {
        return -1;
    }
    if (strlen(dir) >= PATH_MAX) {
        return -1;
    }
    memmove(path, dir, strlen(dir) + 1);
    return 0;
}

int main(void) {
    uint32_t size = PATH_MAX;
    char executable_path[PATH_MAX];
    char project_root[PATH_MAX];
    char launcher_path[PATH_MAX];
    pid_t pid = 0;
    int status = 0;

    if (_NSGetExecutablePath(executable_path, &size) != 0) {
        show_alert("Failed to resolve executable path.");
        return 1;
    }

    if (!realpath(executable_path, project_root)) {
        show_alert("Failed to resolve application path.");
        return 1;
    }

    for (int i = 0; i < 4; i++) {
        if (path_dirname(project_root) != 0) {
            show_alert("Failed to resolve project root.");
            return 1;
        }
    }

    if (snprintf(launcher_path, sizeof(launcher_path), "%s/tools/LTrnsrb.sh", project_root) >= (int)sizeof(launcher_path)) {
        show_alert("Launcher path is too long.");
        return 1;
    }

    if (access(launcher_path, X_OK) != 0) {
        if (errno == ENOENT) {
            show_alert("tools/LTrnsrb.sh was not found next to LTrnsrb.app");
        } else {
            show_alert("tools/LTrnsrb.sh is not executable");
        }
        return 1;
    }

    if (chdir(project_root) != 0) {
        show_alert("Failed to switch to project directory.");
        return 1;
    }

    char *const argv[] = {"/bin/zsh", launcher_path, NULL};
    if (posix_spawn(&pid, "/bin/zsh", NULL, NULL, argv, environ) != 0) {
        show_alert("Failed to start launcher.");
        return 1;
    }

    if (waitpid(pid, &status, 0) < 0) {
        show_alert("Launcher exited unexpectedly.");
        return 1;
    }

    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    return 1;
}
