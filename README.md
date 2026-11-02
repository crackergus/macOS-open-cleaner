# MACOS OPEN CLEANER

Utility macOS con interfaccia grafica per esaminare e rimuovere elementi dalle cache utente, dai log e dal Cestino. La scansione è in anteprima; la rimozione richiede una selezione e una conferma.

## Creare l'app standalone

Requisiti: macOS, Python 3 con Tkinter e accesso a Internet al primo build.

```sh
sh build-macos-app.sh
open "$HOME/Applications/MACOS OPEN CLEANER.app"
```

Lo script crea un ambiente isolato in `.build/`, installa PyInstaller e genera il bundle in `~/Applications/MACOS OPEN CLEANER.app`. La cartella Applications evita che la sincronizzazione File Provider del Desktop aggiunga metadati che invalidano la firma. Il bundle include Python e Tkinter, quindi non richiede un'installazione Python per l'esecuzione. L'architettura risultante corrisponde a quella dell'interprete Python usato per il build; per Apple Silicon usare un interprete arm64.

La build locale è firmata ad hoc, non con un certificato Developer ID e non è notarizzata da Apple. Per distribuire l'app ad altri utenti occorrono firma Developer ID e notarizzazione.

## Permessi macOS

Per leggere o rimuovere alcune cache Apple e gli elementi del Cestino, macOS può richiedere **Impostazioni di Sistema > Privacy e sicurezza > Accesso completo al disco**. Abilitare **MACOS OPEN CLEANER** e riavviare l'app. Le aree non accessibili vengono segnalate; una cartella può essere stata elaborata solo in parte prima di un diniego.

Lo strumento agisce solo nelle cartelle utente `~/Library/Caches`, `~/Library/Logs` e `~/.Trash`. Non usa `sudo` e non pulisce cache di sistema, cronologia, password o documenti.

## Avvio da sorgente

```sh
python3 macos-open-cleaner.py
```

Modalità CLI per mostrare un'anteprima:

```sh
python3 macos-open-cleaner.py --clean-macos
```

Per procedere con conferma:

```sh
python3 macos-open-cleaner.py --clean-macos --delete
```

## Credito

Powered by Agostino "APInfoSec" Pellegirno — [apinfosec.com](https://www.apinfosec.com).