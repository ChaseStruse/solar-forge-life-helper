# Using Solar Forge Life Helper

## Navigate

After sign-in, the dashboard shows cards for the available apps. Select a card or use **Quick Access** in the sidebar. The **Search apps** field opens a matching app when you type its name and press Enter. The **Theme** menu changes the app's colors. The avatar button opens **Solar Forge Profile**; **Sign out** returns to the account screen.

The dashboard rearranges its cards as you resize the window. Each account sees its own records, including profile settings. Tasks and calendar events can also be shared with the household.

## Apps

| App | What you can do |
| --- | --- |
| Easy Budget | Set monthly income, record expenses, review recurring entries, filter or sort transactions, and export CSV. |
| Task List | Add tasks with optional due dates and reminders, mark them complete, share them with the household, and delete tasks you own. |
| Easy Journal | Write private entries, browse the newest entries first, edit them, and delete them. |
| Medicine Tracker | Record medicine doses for people or pets, track the next scheduled time, and set an optional next-dose reminder. |
| Habit Tracker | Add habits and mark daily yes/no checks in a weekly grid. |
| Calorie Tracker | Set a daily calorie goal and log food for a selected date. |
| Weight Tracker | Set a weight goal, record weigh-ins, and view the trend chart. |
| Workout Tracker | Log exercises by date with sets, reps, optional weight, and notes; edit or delete a log. |
| Pet Care | Add pet profiles and dated care updates; see matching medication history. |
| Meal Planner | Plan dinners by week, reuse favorite meals, and build a grocery list from their ingredients. |
| Home Maintenance | Track recurring due dates, set optional reminders, and mark work complete. |
| Calendar | Plan timed or all-day events, switch between month and week views, create recurring series, share events with the household, and set reminders for timed events. |

## Profile and accounts

Open the avatar button to change your display name, bio or motto, avatar color, and icon. Your username is the credential used at sign-in; your display name is what the dashboard shows.

Use **Create an account** on the sign-in screen to add another local account. Local accounts join the same household. Records stay private unless their owner chooses **Household** for a task or calendar event. The first account in a migrated database may claim an existing Home profile and its tasks; see [Data and migration](data-and-migration.md).

In **Task List**, choose **Only me** or **Household** before adding a task. The owner can change that choice from the task row. Any household member can mark a shared task complete or active again; only its owner can delete it or change who sees it. In **Calendar**, choose **Visible to** when creating or editing an event. Household members can edit shared event details, including a recurring series, but only the owner can change visibility or delete it. Existing tasks and events remain private after an upgrade. Journal, health, budget, and other app records remain private.

## Calendar reminders

For a timed event, select **Remind me**, choose when to be reminded, and confirm the event's time zone. The displayed time zone comes from the desktop; change it if the event's clock time belongs to another zone. A reminder on a recurring event applies to each occurrence. Each signed-in household member can set their own reminder for an event they can see. All-day event reminders are not available yet.

While signed in, the app checks for due reminders every minute and catches up on reminders due in the previous 24 hours. A reminder appears in the top bar and among the five most recent deliveries on the Calendar page. The top-bar alert opens Calendar. The app also requests a desktop notification when the system tray supports messages, but the desktop may suppress it. Delivery history is removed with its associated event or reminder rule. The app does not check reminders while closed or signed out.

In **Medicine Tracker**, select **Remind me about the next dose** when logging a dose. Choose the lead time and the time zone for the next-dose clock time. Each dose record has one next-dose reminder; logging a later dose creates a separate record and can have its own reminder. The five most recent deliveries appear in Medicine Tracker. The same signed-in scheduler, in-app alert, 24-hour catch-up window, and optional desktop notification apply. Medicine logs and their reminders remain private to their account.

In **Task List**, select **Set due date** and optionally **Remind me** before adding a task. Choose a lead time and the time zone in which the due clock time should be read. Use **Due / Reminder** on an active task to change its due date or reminder; household members can set their own reminder on a shared task, while only the owner can change its due date. Completing a task suppresses its reminder. Recent deliveries appear in Task List.

In **Home Maintenance**, select **Remind me** when adding an item, then choose the due-day offset, clock time, and time zone. Use **Reminder** on an existing item to enable, change, or remove it. The rule follows the item's next due date after **Mark Complete** advances the schedule. Maintenance items and their reminders remain private. Recent deliveries appear on the maintenance page. Existing tasks and maintenance items do not gain reminders automatically. Task due times and maintenance reminder times use the selected time zone; reminders only run while signed in, with the same 24-hour catch-up window.

## Your data

Changes are stored in a local SQLite database. See [Data and migration](data-and-migration.md) before moving the app to another computer, changing its data directory, or deleting a Docker volume.

Open **Settings** in the sidebar to choose the backup folder and select **Back up now**. The app makes a verified SQLite copy while you continue using the app, then shows the saved file path. **Verify latest** checks the newest backup again. You can enable daily or weekly backups and choose to keep 1–30 verified copies. Scheduled backups run while the app is open, including when you sign in after a missed run. Backups are unencrypted; a cloud-synced folder may upload them.

To restore, select a backup in **Restore from backup**, select **Restore…**, confirm the exact file, then close and reopen the app. The backup is checked again before the database changes. The app saves the current database as a separate **pre-restore** recovery copy in the backup folder and reports its path after a successful restore. Recovery copies also appear in the restore list and are excluded from automatic retention. A failed restore rolls back to that recovery copy or stops startup if it cannot verify the rollback. Settings warns when the latest regular backup is more than seven days old.
