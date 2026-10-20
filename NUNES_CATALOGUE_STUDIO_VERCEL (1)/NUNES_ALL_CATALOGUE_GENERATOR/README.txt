NUNES ALL CATALOGUE GENERATOR - DIRECT DRIVE VERSION
=====================================================

PURPOSE
- Reads product names directly from the Google Drive spreadsheet: "total price list".
- Configured spreadsheet ID: 1jYUA7SqSBlkGUs-IaybfEM8lI1ors2w3h62z8yYLC5I
- Sheet: Sheet1
- Product Name: column E
- Model: column F
- Specifications: column G
- Existing image link: column D
- The Drive sheet has 127,346 rows in the current configuration.

OUTPUT ONLY
1. Catalogue\               -> one full Nunes catalogue PDF per unique Product Name + Model
2. Mini Catalogue\          -> one related-products mini catalogue PDF per unique Product Name + Model

NO EXCEL QUEUE IS CREATED.
The product source remains Google Drive.

ACCURACY / SEARCH ORDER
1. Read exact Product Name + Model + Specifications + Image Link from Drive.
2. Use the Drive image link first when valid.
3. Search exact Product Name + Model on the web only when more details are required.
4. Prefer an exact matching product page / datasheet.
5. IndiaMART search is a fallback when normal search does not provide enough details.
6. The generator never invents numeric technical values when strict_accuracy=true.
7. If an exact image cannot be verified, the PDF shows "PRODUCT IMAGE pending exact-model verification" instead of using a fake image.

MINI CATALOGUE
- Related products are selected from the SAME Drive product list.
- Similar product words/categories are used to select up to 10 related items.
- Their Drive image links are tried first, then exact web image search.

HOW TO CONNECT GOOGLE DRIVE
Preferred: copy your existing google_service_account.json into this folder or into a config\ folder.
The "total price list" Google Sheet must be shared with the service-account email.

Alternative: place client_secret.json in this folder. On first run, Google OAuth opens in the browser and saves token.json locally.

If the sheet is public, the program can also try the direct Google CSV export automatically.

WINDOWS
Double-click: START_GENERATE_ALL_WINDOWS.bat

MAC / LINUX
Run: ./start_mac_linux.sh

RESUME / LONG RUN
- All products are processed sequentially, one by one.
- progress.sqlite3 stores only generation status so the job can resume safely.
- Close the window at any time. Run START_GENERATE_ALL_WINDOWS.bat again to continue.
- Existing completed PDFs are skipped automatically.

IMPORTANT
Generating tens of thousands of exact researched product catalogues is a long-running job and can take many hours or days depending on web speed/rate limits. This package is specifically built to continue until the complete Drive list is processed rather than stopping after a small fixed batch.
