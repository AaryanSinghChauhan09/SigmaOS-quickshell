    # SigmaOS-quickshell

    Quick shell command runner

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/omacom/quickshell

    ## Design principles applied
    - **Separation of Concerns**
- **Least Astonishment**
- **Defensive Programming**
- **Fail-Fast**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `run-plan, history, alias, scripts`

    ```
    $ sigma-quick run-plan "ls -la" --cwd /tmp
ls -la
$ sigma-quick run-plan "ls | wc -l" --shell
/bin/sh -c 'ls | wc -l'
$ sigma-quick history ~/.local/state/sigma-quick/history --record "git status"
$ sigma-quick alias ~/.config/sigma-quick/aliases --add gs='git status'
$ sigma-quick scripts ~/.local/share/sigma-quick/scripts
backup :: backup the home directory

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
