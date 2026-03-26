# Attendance_Streamlit_App

This is used for calculating clinic attendance

## Todo List

* [ ] Add the `Employee Shift List` and `Employee Shift Settings`, to further validate the period and filter out unnecessary duty entries, overtime entries, late entries. When filtering out any of the entries, we send warning on the UI
* [X] Add the `Metadata` section in UI sidebar to let user to enter `Period Start Time`, `Period End Time`, `Period Overtime Start Time`, `Period Late Start Time`, and implement a memory feature so users don't have to enter over and over again. Use a `config.json` to store metadata when hitting `Analyze Data` button
* [ ] Create an icon for the app (windows: `.ico`, mac: `.icn`)
* [X] Add a `Show Calendar` button on sidebar. After hitting it, it shows a calendar object, and show all of leave records for all employee. (Use [streamlit-calendar](https://github.com/im-perativa/streamlit-calendar))
* [X] Add google sheet URL in the UI
* [ ] If we find overtime records in `On Duty Entries` , but there are no records on `Overtime Details`, then we show a yellow warning message that there are records missing or need to be fixed. If not, we don't count those overtime durations
  * I think we should leave it as manual inspections
* [X] Check all of the entries for all inputs, we base on swiping records, and shift settings, then check overtime. If there are records missing, we show yellow warning messages highlighting users
* [X] In google sheet, if there are string `###` in front of values of column `加班時處理的病人姓名 or 水藥編號`, we count the overtime as invalid. So maybe in `Overtime Detail`, we need a column `Validility` to indicate if the entry is valid or not
* [ ] We need a button, `Download PDF` , to contain all of the tables for each employee
* [ ] Update `README.md` when the system is ready for production
* [ ] Make a branch and translate the UI layout to Mandarin
