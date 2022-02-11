"""
Command line interface for working with profiles
"""
import textwrap
from typing import List

import toml
import typer

import prefect.context
import prefect.settings
from prefect.cli.base import (
    PrefectTyper,
    app,
    console,
    exit_with_error,
    exit_with_success,
)
from prefect.utilities.collections import dict_to_flatdict

config_app = PrefectTyper(
    name="config", help="Commands for interacting with the Prefect configuration."
)
app.add_typer(config_app)


@config_app.command()
def get_profile(names: List[str] = typer.Argument(None)):
    """
    Show settings in a profile or multiple profiles. Defaults to the current profile.
    """
    profiles = prefect.context.load_profiles()
    if not names:
        profile = prefect.context.get_profile_context()
        names = [profile.name]

    display_profiles = {
        name: values for name, values in profiles.items() if name in names
    }
    console.out(toml.dumps(display_profiles).strip())


@config_app.command()
def get_profiles():
    """
    Show settings in all profiles.
    """
    profiles = prefect.context.load_profiles()
    console.out(toml.dumps(profiles).strip())


@config_app.command()
def list_profiles():
    """
    List profile names.
    """
    profiles = prefect.context.load_profiles()
    current = prefect.context.get_profile_context().name
    for name in profiles:
        if name == current:
            console.print(f"* {name}")
        else:
            console.print(name)


@config_app.command()
def set(variables: List[str]):
    """
    Set a value in the current configuration profile.
    """
    profiles = prefect.context.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    parsed_variables = []
    for variable in variables:
        try:
            var, value = variable.split("=")
        except ValueError:
            exit_with_error(
                f"Failed to parse argument {variable!r}. Use the format 'VAR=VAL'."
            )

        parsed_variables.append((var, value))

    for var, value in parsed_variables:
        env[var] = value
        console.print(f"Set variable {var!r} to {value!r}")

    prefect.context.write_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}")


@config_app.command()
def unset(variables: List[str]):
    """
    Set a value in the current configuration profile.
    """
    profiles = prefect.context.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    for var in variables:
        if var not in env:
            exit_with_error(f"Variable {var!r} not found in profile {profile.name!r}.")
        env.pop(var)

    for var in variables:
        console.print(f"Unset variable {var!r}")

    prefect.context.write_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}")


@config_app.command()
def create_profile(
    name: str,
    from_name: str = typer.Option(None, "--from", help="Copy an existing profile."),
):
    """
    Create a new profile.
    """
    usage = textwrap.dedent(
        f"""
        To use your profile, set an environment variable:

            export PREFECT_PROFILE={name!r}

        or include the profile in your CLI commands:

            prefect -p {name!r} config view
        """
    ).rstrip()

    profiles = prefect.context.load_profiles()
    if name in profiles:
        console.print(
            f"[red]Profile {name!r} already exists.[/red]"
            + usage
            + textwrap.dedent(
                f"""

                To create a new profile, remove the existing profile first:

                    prefect config rm-profile {name!r}
                """
            ).rstrip()
        )
        raise typer.Exit(1)

    if from_name:
        if from_name not in profiles:
            exit_with_error("Profile {from_name!r} not found.")

        profiles[name] = profiles[from_name]
        from_blurb = f" matching {from_name!r}"
    else:
        from_blurb = ""
        profiles[name] = {}

    prefect.context.write_profiles(profiles)
    console.print(f"[green]Created profile {name!r}{from_blurb}.[/green] {usage}")


@config_app.command()
def rm_profile(name: str):
    """
    Remove the given profile.
    """
    profiles = prefect.context.load_profiles()
    if name not in profiles:
        exit_with_error(f"Profle {name!r} not found.")

    profiles.pop(name)

    verb = "Removed"
    if name == "default":
        verb = "Reset"
        profiles["default"] = {}

    prefect.context.write_profiles(profiles)
    exit_with_success(f"{verb} profile {name!r}.")


@config_app.command()
def rename_profile(name: str, new_name: str):
    """
    Change the name of a profile.
    """
    profiles = prefect.context.load_profiles()
    if name not in profiles:
        exit_with_error(f"Profle {name!r} not found.")

    if new_name in profiles:
        exit_with_error(f"Profile {new_name!r} already exists.")

    profiles[new_name] = profiles.pop(name)

    prefect.context.write_profiles(profiles)
    exit_with_success(f"Renamed profile {name!r} to {new_name!r}.")


@config_app.command()
def view(show_defaults: bool = False, show_sources: bool = False):
    """
    Display the current configuration.
    """
    profile = prefect.context.get_profile_context()

    # Get settings at each level, converted to a flat dictionary for easy comparison
    default_settings = dict_to_flatdict(prefect.settings.defaults().dict())
    env_settings = dict_to_flatdict(prefect.settings.from_env().dict())
    current_settings = dict_to_flatdict(profile.settings.dict())

    output = [f"PREFECT_PROFILE={profile.name!r}"]

    # Collect differences from defaults set in the env and the profile
    env_overrides = {
        "PREFECT_" + "_".join(key).upper(): val
        for key, val in env_settings.items()
        if val != default_settings[key]
    }

    current_overrides = {
        "PREFECT_" + "_".join(key).upper(): val
        for key, val in current_settings.items()
        if val != default_settings[key]
    }

    for key, value in current_overrides.items():
        source = "env" if value == env_overrides.get(key) else "profile"
        source_blurb = f" (from {source})" if show_sources else ""
        output.append(f"{key}='{value}'{source_blurb}")

    if show_defaults:
        for key, value in sorted(default_settings.items()):
            key = "PREFECT_" + "_".join(key).upper()
            source_blurb = f" (from defaults)" if show_sources else ""
            output.append(f"{key}='{value}'{source_blurb}")

    console.print("\n".join(output))
