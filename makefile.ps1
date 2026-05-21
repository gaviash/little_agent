param(
    [string]$Command = "help"
)
switch ($Command) {
    "run" {
        fastapi app/main.py
    }

    "test" {
        pytest tests -q
    }

    "lint" {
        ruff check
    }

    "install" {
        pip install -r requirements.txt
    }

    default {
        Write-Host "Commande inconnue: $Command"
        Write-Host ""
        Write-Host "Commandes disponibles:"
        Write-Host "  .\dev.ps1 run"
        Write-Host "  .\dev.ps1 test"
        Write-Host "  .\dev.ps1 lint"
        Write-Host "  .\dev.ps1 install"
    }
}