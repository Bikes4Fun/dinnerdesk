# Repository organization

This proprietary portfolio repository contains application code, tests, maintained documentation, build inputs. Real recipes, photos, trained model data, research, screenshots and exports belong in private storage outside Git.

## Completed separation

- Private catalog assets were preserved in `../dd_support/catalog/dinnerdesk/`, with a checksum manifest for 153 files.
- Runtime readers require external private catalog and photo directories. Employers can view and test the live application.
- Railway startup no longer imports recipe files. Existing PostgreSQL records remain independent of Git.
- `LICENSE` states the proprietary portfolio policy. Bundled font licenses are retained in THIRD_PARTY_NOTICES.md and the fonts directory.
- Legacy `/data/`, `/food/` and `/tastelab/data/` directories are ignored along with credentials, exports, dependencies and generated builds.

See [Catalog storage](CATALOG_STORAGE.md) for local configuration and the required private asset upload before Railway deployment. Keep `dd_support` private and backed up. The earlier screenshot cleanup manifest remains in its `review/dinnerdesk/` directory.

## Remaining maintenance

Keep [TESTER_CHECKLIST.md](TESTER_CHECKLIST.md) current. Keep product requirements in DESIGN.md and TODO.md, and move personal research and screenshot history into `dd_support`. Review Python dependency locking separately before a release. Verify third-party asset permission records rather than inventing them.

The recovered Git repository has no old commits or configured remote. Ignoring files cannot erase information from a separate existing public remote; any such remote requires its own history review before publication.
