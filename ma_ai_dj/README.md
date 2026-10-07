# Native MA integration — development source only

**User requirement: retain the official public Music Assistant release and its normal updates.**

The replacement MA HA add-on has been withdrawn. Do not replace or migrate the existing Music Assistant installation for this project. There is no installable MA replacement in this directory.

MA 2.10.5 loads plugin providers from its packaged server source. Its frontend has no external extension point for our new Party search controls. Adding a provider to the code and patching PartyGuestView is a customized build, not a GitHub-installable plugin for stock MA.

## Supported architecture

The existing **Party AI DJ** HA add-on runs independently and searches/enqueues through the existing official MA API. The **Kiosk Satellite Party Mode** plugin can use this companion API without altering Music Assistant. Home Assistant switches continue to control the Kiosk search modes.

Custom AI controls on desktop or guest phones require a separate companion web interface, or eventual inclusion of the native integration in official MA. The stock MA guest page remains its normal page; updating this repository does not insert AI search into it. The user's choice of desktop/guest interface has not yet been settled.

## Preserved development work

`provider/`, `frontend.patch`, `frontend/PartyAiSearch.vue`, `apply.py`, `upstream.json` and `check_contract.py` are preserved as source for possible upstream development. They are pinned to MA 2.10.5 and frontend 2.17.297. They are not the installation route for the user's server.

```sh
python -m unittest discover -s ma_ai_dj/tests -v
python ma_ai_dj/check_contract.py --server /path/to/ma-server
```

The tests and patched-frontend build validate development code only; they do not establish compatibility as an external stock-MA plugin.
