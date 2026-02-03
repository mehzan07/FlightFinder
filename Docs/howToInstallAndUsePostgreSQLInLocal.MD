How to install and use PostgreSQL in local machine?
  nstall PostgreSQL on Windows
  1- Download PostgreSQL Installer for Windows
First, go to the download page of PostgreSQL installers on the EnterpriseDB.
  Install PostgreSQL on Windows step-by-step
To install PostgreSQL on Windows, you need to have administrator privileges.

Step 1. Double-click on the installer file and an installation wizard will appear and guide you through multiple steps. Hence, you can choose various options based on your preferences for PostgreSQL.
  Step 2. Click the Next button
Step 3. Specify the installation directory by either choosing your preferred location or using the default folder suggested by the PostgreSQL installer and click the Next button
tep 4. Select software components to install
Step 5. Choose the database directory to store the data,
Step 6. Enter the password for the database superuser (postgres).
Step 7. Specify a port number on which the PostgreSQL database server will listen. The default port of PostgreSQL is 5432. Ensure that no other applications are using this port.

Step 8. Select the default locale for the PostgreSQL server. If you leave it as the default, PostgreSQL will use the operating system locale. Afterward, click the Next button.
Step 9. The setup wizard will show the summary PostgreSQL information. Review the details, and if everything is correct, click the Next button. Otherwise, click the Back button to adjust the configuration accordingly.

  How to access to PostgreSQL in local machine?
  1- start pgAdmin from start of Window
  2- click Object Explorer: Servers: Databases: your Database (e.g. chatbot_db): Schemas: Tables: your table (e.g: chat). 
  3- right click on table (chat) and press to uder menu: View /Edit Data: All Rows (or 100 first etc)
  4- you see your tables contains
