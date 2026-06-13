from dataclasses import dataclass

from .launch_manager import LaunchCancelled, LaunchError, launch_game


@dataclass(frozen=True)
class LaunchExecutionResult:
    success: bool
    cancelled: bool
    message: str
    level: str


def execute_launch_config(config=None):
    try:
        launch_game(config)
    except LaunchCancelled as error:
        return LaunchExecutionResult(
            success=False,
            cancelled=True,
            message=str(error),
            level="info",
        )
    except (LaunchError, ValueError, OSError) as error:
        return LaunchExecutionResult(
            success=False,
            cancelled=False,
            message=str(error),
            level="error",
        )

    return LaunchExecutionResult(
        success=True,
        cancelled=False,
        message="Jogo iniciado.",
        level="success",
    )


__all__ = ["LaunchExecutionResult", "execute_launch_config"]
