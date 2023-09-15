"""An interface to interact with Replit's code-exec API."""

import logging
from typing import Any, Dict, Optional

import instructor  # type: ignore
import requests


def code_exec(
    url: str,
    bearer_token: str,
    code: str,
    files: Optional[Dict[str, str]] = None,
    strace: bool = False,
    interpreter_mode: bool = False,
) -> str:
    """Evaluates a snippet of Python code in a sandbox.

    This is an interface for the simpler use cases of https://replit.com/@luisreplit/eval-python. In
    general, this allows executed an untrusted snippet of Python code and returns whatever is
    printed to standard output / standard error as the result. The execution is done inside an
    ephemeral unprivileged container created on the fly running in Replit Deployments using
    https://github.com/omegaup/omegajail as code sandbox.

    To set up your own copy of the API server, you need to follow these easy 2-3 steps (the second
    is optional):

    1. Open the https://replit.com/@luisreplit/eval-python in your browser and Fork it to your
       account.
    2. (Optional): if you want to change the Docker container, run `evalctl image ${DOCKER_IMAGE}`
       (e.g. `evalctl image python:3` or `evalctl image replco/python-kitchen-sink:latest`).
        * Open `.replit` and change the `EVAL_FILENAME`, `EVAL_RUN_COMMAND`, `EVAL_ENV` to suite the
          new container, if needed.
    3. Deploy the Repl! (just pressing `Run` is not enough)
        * This is only compatible with the Autoscale Deployments.
        * Make sure you set the `EVAL_TOKEN_AUTH` Deployments secrets when
          doing so for authentication.

    Args:
        url: The URL of the Deployed version of your fork of
             https://replit.com/@luisreplit/eval-python
        bearer_token: The contents of the `EVAL_TOKEN_AUTH`  Deployments secret.
        code: The snippet of Python code that will be evaluated.
        files: (Optional): a map of filenames -> contents that will be written to the current
             directory where the Python code will be executed.
        strace: (Optional): For debugging purposes, run `strace` before executing the code.
        interpreter_mode: (Optional): Sometimes it is desirable to avoid needing to explicitly call
            `print()` to get access to the values that are evaluated. When this option is enabled,
            the sandbox will behave like the `python` CLI interpreter, where any expressions are
            output into standard output.

    Returns:
        A string containing the standard output / standard input printed during the execution of
        `code`.
    """
    data: Dict[str, Any] = {"code": code}
    if files is not None:
        data["files"] = files
    if strace:
        data["strace"] = True
    if interpreter_mode:
        data["interpreter_mode"] = True
    return requests.post(
        url,
        json=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + bearer_token,
        },
    ).text


def build_code_exec(
    url: str,
    bearer_token: str,
    files: Optional[Dict[str, str]] = None,
    strace: bool = False,
    interpreter_mode: bool = False,
) -> instructor.openai_function:
    """An ergonomic way to use `code_exec` with the OpenAI API.

    Sample usage:

    import openai
    import replit_code_exec

    code_exec = replit_code_exec.build_code_exec(...)

    def solve_math(prompt: str, model: str = 'gpt-3.5-turbo-0613') -> str:
        completion = openai.ChatCompletion.create(
            model=model,
            temperature=0.7,
            functions=[code_exec.openai_schema],
            function_call={"name": "code_exec"},
            messages=[
                {
                    "role": "system",
                    "content": ("You are an assistant that knows how to solve math " +
                                "problems by converting them into Python programs."),
                },
                {
                    "role": "user",
                    "content": ("Please solve the following problem by creating a Python " +
                                "program that prints the solution to standard output using " +
                                "`print()`: " + prompt),
                },
            ],
        )
        return code_exec.from_response(completion)

    See the documentation of `code_exec` for more information.

    Args:
        url: The URL of the Deployed version of your fork of
             https://replit.com/@luisreplit/eval-python
        bearer_token: The contents of the `EVAL_TOKEN_AUTH`  Deployments secret.
        files: (Optional): a map of filenames -> contents that will be written to the current
             directory where the Python code will be executed.
        strace: (Optional): For debugging purposes, run `strace` before executing the code.
        interpreter_mode: (Optional): Sometimes it is desirable to avoid needing to explicitly call
            `print()` to get access to the values that are evaluated. When this option is enabled,
            the sandbox will behave like the `python` CLI interpreter, where any expressions are
            output into standard output.

    Returns:
        A `instructor.openai_function`-wrapped function that can be used with
        OpenAI's function invocation API.
    """

    @instructor.openai_function  # type: ignore
    def _code_exec(code: str) -> str:
        """
        Evaluates an arbitrary snippet of Python code. This is useful if you want answer to
        a computation that can be answered by creating a standalone Python code that prints
        the answer to standard output.

        In order to use it, you need to specify the code as if it were the contents of a
        file called main.py with no code fences and run with the Python interpreter as
        `python3 main.py`. The answer should be printed to standard output.

        Some things to note:
        - There are no other files in the current directory. This means that any attempt to
        open() files will fail.
        - Make sure the code is optimized so that it runs fast. Try to use memoization.
        - Always call print() with the final result so that it is printed to standard
        output.

        Bad response:
        ```python
        1 + 1
        ```

        Good response:
        import urllib.request
        print(urllib.request.urlopen(\"https://ifconfig.me\").read().decode(\"utf-8\"))
        """
        code = code.strip()
        if code.startswith("```") and code.endswith("```"):
            # We told the agent to not add code fences and it ignored us >:(
            code = "\n".join(code.split("\n")[1:-1])
        response = code_exec(url, bearer_token, code, files, strace, interpreter_mode)
        logging.debug("code to evaluate %r, response %r", code, response)
        return response

    return _code_exec
