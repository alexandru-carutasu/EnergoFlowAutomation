"""
EvalFileManager - Service for creating and updating evaluation files.

Handles evaluation file operations including creation from templates,
data merging, and uploading to Dropbox.
"""

import logging
import os
import tempfile
from datetime import datetime as dt, timedelta
from typing import Optional, List

import pandas as pd
from openpyxl import load_workbook

from services.dropboxclient.DropboxClient import DropboxClient
from services.dbmanager.DbManager import DbManager

logger = logging.getLogger(__name__)


class EvalFileManager:
    """Manages evaluation file creation and updates."""

    EVAL_FILE_PREFIX = "Evaluare_"
    EVAL_FILE_SUFFIX = ".xlsx"
    EVAL_FOLDER_TEMPLATE = "/Forecast automat/{client_name}"
    TEMPLATE_FOLDER = "/Forecast automat/Template"
    TEMPLATE_FILE_NAME = "Evaluare_template.xlsx"

    def __init__(self, db_manager: DbManager, dropbox_client: DropboxClient) -> None:
        """Initialize EvalFileManager.

        Parameters
        ----------
        db_manager : DbManager
            Database manager instance
        dropbox_client : DropboxClient
            Dropbox client for file operations
        """
        self.db_manager = db_manager
        self.dropbox_client = dropbox_client

    def create_evaluation_file(
        self, client_id: int, client_name: str, date_str: str
    ) -> bool:
        """Create evaluation file for client and month.

        Parameters
        ----------
        client_id : int
            Client ID
        client_name : str
            Client name
        date_str : str
            Date in MMYYYY format

        Returns
        -------
        bool
            True if successful
        """
        logging.info(f"Creating evaluation file for {client_name} - {date_str}")
        try:
            # Get plant names from database
            plants = self.db_manager.get_plants_by_client(client_id)
            if not plants:
                logging.warning(f"No plants found for client {client_id}")
                return False

            plant_names = [plant.name for plant in plants]

            # Download template from Dropbox
            template_path = self._download_template()
            if not template_path:
                logging.error("Failed to download template from Dropbox")
                return False

            # Create evaluation file from template
            local_file_name = f"{self.EVAL_FILE_PREFIX}{client_name}_{date_str}{self.EVAL_FILE_SUFFIX}"
            eval_file_path = self._create_eval_file_from_template(
                template_path, local_file_name, plant_names, date_str
            )

            if not eval_file_path:
                logging.error("Failed to create evaluation file")
                if os.path.exists(template_path):
                    os.remove(template_path)
                return False

            # Upload to Dropbox
            dropbox_folder = self.EVAL_FOLDER_TEMPLATE.format(client_name=client_name)
            upload_result = self.dropbox_client.upload_excel_to_dropbox(
                eval_file_path, dropbox_folder
            )

            # Cleanup
            try:
                os.remove(template_path)
                os.remove(eval_file_path)
            except OSError as e:
                logging.warning(f"Error cleaning up files: {e}")

            if not upload_result:
                logging.error(f"Failed to upload evaluation file to Dropbox")
                return False

            logging.info(f"Successfully created evaluation file for {client_name}")
            return True

        except Exception as e:
            logging.error(f"Error creating evaluation file: {e}", exc_info=True)
            return False

    def update_evaluation_files(
        self, client_name: str, client_id: int, curr_date: dt
    ) -> bool:
        """Update evaluation files for multi-plant client.

        Parameters
        ----------
        client_name : str
            Client name
        client_id : int
            Client ID
        curr_date : datetime
            Current date

        Returns
        -------
        bool
            True if successful
        """
        logging.info(f"Updating evaluation files for {client_name}")
        try:
            # Download existing evaluation file
            formatted_date = curr_date.strftime("%m%Y")
            eval_file_path = self._download_eval_file(client_name, formatted_date)

            if not eval_file_path or not os.path.exists(eval_file_path):
                logging.error(f"Failed to download evaluation file from Dropbox")
                return False

            # Get all plants for client
            plants = self.db_manager.get_plants_by_client(client_id)

            for plant in plants:
                self._update_plant_sheet(eval_file_path, plant.id, plant.name, curr_date)

            # Upload updated file
            dropbox_folder = self.EVAL_FOLDER_TEMPLATE.format(client_name=client_name)
            upload_result = self.dropbox_client.upload_excel_to_dropbox(
                eval_file_path, dropbox_folder
            )

            if upload_result:
                logging.info(f"Successfully updated evaluation file for {client_name}")
                try:
                    os.remove(eval_file_path)
                except OSError:
                    pass
                return True
            else:
                logging.error("Failed to upload updated evaluation file to Dropbox")
                return False

        except Exception as e:
            logging.error(f"Error updating evaluation files: {e}", exc_info=True)
            return False

    def update_evaluation_files_1plant(
        self, client_name: str, client_id: int, plant_name: str, curr_date: dt
    ) -> bool:
        """Update evaluation file for single plant.

        Parameters
        ----------
        client_name : str
            Client name
        client_id : int
            Client ID
        plant_name : str
            Plant name
        curr_date : datetime
            Current date

        Returns
        -------
        bool
            True if successful
        """
        logging.info(
            f"Updating evaluation file for {client_name} - plant {plant_name}"
        )
        try:
            # Download existing evaluation file
            formatted_date = curr_date.strftime("%m%Y")
            eval_file_path = self._download_eval_file(client_name, formatted_date)

            if not eval_file_path or not os.path.exists(eval_file_path):
                logging.error(f"Failed to download evaluation file from Dropbox")
                return False

            # Get plant ID
            plants = self.db_manager.get_plants_by_client(client_id)
            plant_id = None
            for plant in plants:
                if plant.name == plant_name:
                    plant_id = plant.id
                    break

            if plant_id is None:
                logging.error(f"Plant {plant_name} not found for client {client_id}")
                return False

            # Update sheet for this plant
            self._update_plant_sheet(eval_file_path, plant_id, plant_name, curr_date)

            # Upload updated file
            dropbox_folder = self.EVAL_FOLDER_TEMPLATE.format(client_name=client_name)
            upload_result = self.dropbox_client.upload_excel_to_dropbox(
                eval_file_path, dropbox_folder
            )

            if upload_result:
                logging.info(
                    f"Successfully updated evaluation file for {plant_name}"
                )
                try:
                    os.remove(eval_file_path)
                except OSError:
                    pass
                return True
            else:
                logging.error("Failed to upload updated evaluation file to Dropbox")
                return False

        except Exception as e:
            logging.error(f"Error updating evaluation file for 1 plant: {e}", exc_info=True)
            return False

    def update_evaluation_file(
        self, client_name: str, client_id: int, curr_date: dt
    ) -> bool:
        """Update evaluation file by updating all plants.

        Parameters
        ----------
        client_name : str
            Client name
        client_id : int
            Client ID
        curr_date : datetime
            Current date

        Returns
        -------
        bool
            True if successful
        """
        logging.info(f"Updating evaluation file for {client_name}")
        try:
            plants = self.db_manager.get_plants_by_client(client_id)
            if not plants:
                logging.warning(f"No plants found for client {client_id}")
                return False

            for plant in plants:
                self.update_evaluation_files_1plant(
                    client_name, client_id, plant.name, curr_date
                )

            return True
        except Exception as e:
            logging.error(f"Error updating evaluation file: {e}", exc_info=True)
            return False

    # ─────────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────

    def _download_template(self) -> Optional[str]:
        """Download template evaluation file from Dropbox."""
        try:
            refresh_token = self.dropbox_client.load_refresh_token()
            if not refresh_token:
                logging.error("Refresh token not found")
                return None

            dbx = self.dropbox_client.get_access_token(refresh_token)
            if not dbx:
                logging.error("Failed to authenticate with Dropbox")
                return None

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                suffix=".xlsx", delete=False
            ) as tmp_file:
                tmp_path = tmp_file.name

            try:
                template_dropbox_path = f"{self.TEMPLATE_FOLDER}/{self.TEMPLATE_FILE_NAME}"
                metadata, response = dbx.files_download(template_dropbox_path)

                with open(tmp_path, "wb") as f:
                    f.write(response.content)

                logging.info(f"Downloaded template from {template_dropbox_path}")
                return tmp_path
            except Exception as e:
                logging.error(f"Error downloading template from Dropbox: {e}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return None

        except Exception as e:
            logging.error(f"Error in _download_template: {e}")
            return None

    def _download_eval_file(self, client_name: str, date_str: str) -> Optional[str]:
        """Download existing evaluation file from Dropbox."""
        try:
            refresh_token = self.dropbox_client.load_refresh_token()
            if not refresh_token:
                logging.error("Refresh token not found")
                return None

            dbx = self.dropbox_client.get_access_token(refresh_token)
            if not dbx:
                logging.error("Failed to authenticate with Dropbox")
                return None

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                suffix=".xlsx", delete=False
            ) as tmp_file:
                tmp_path = tmp_file.name

            try:
                dropbox_path = f"{self.EVAL_FOLDER_TEMPLATE.format(client_name=client_name)}/{self.EVAL_FILE_PREFIX}{client_name}_{date_str}{self.EVAL_FILE_SUFFIX}"
                metadata, response = dbx.files_download(dropbox_path)

                with open(tmp_path, "wb") as f:
                    f.write(response.content)

                logging.info(f"Downloaded evaluation file from {dropbox_path}")
                return tmp_path
            except Exception as e:
                logging.error(f"Error downloading evaluation file from Dropbox: {e}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return None

        except Exception as e:
            logging.error(f"Error in _download_eval_file: {e}")
            return None

    def _create_eval_file_from_template(
        self, template_path: str, output_file_name: str, plant_names: List[str], date_str: str
    ) -> Optional[str]:
        """Create evaluation file from template.

        Parameters
        ----------
        template_path : str
            Path to template file
        output_file_name : str
            Output file name
        plant_names : List[str]
            List of plant names (sheet names)
        date_str : str
            Date in MMYYYY format

        Returns
        -------
        Optional[str]
            Path to created file or None
        """
        try:
            workbook = load_workbook(template_path)

            # Remove default sheet if exists
            if "Sheet" in workbook.sheetnames:
                workbook.remove(workbook["Sheet"])

            # Copy template sheets for each plant
            for plant_name in plant_names:
                if "Template" in workbook.sheetnames:
                    template_sheet = workbook["Template"]
                    new_sheet = workbook.copy_worksheet(template_sheet)
                    new_sheet.title = plant_name

            # Remove template sheet if still exists
            if "Template" in workbook.sheetnames:
                workbook.remove(workbook["Template"])

            # Save file
            workbook.save(output_file_name)
            logging.info(f"Created evaluation file: {output_file_name}")
            return output_file_name

        except Exception as e:
            logging.error(f"Error creating evaluation file from template: {e}")
            return None

    def _update_plant_sheet(
        self, eval_file_path: str, plant_id: int, plant_name: str, curr_date: dt
    ) -> bool:
        """Update sheet for specific plant with measurements and prices.

        Parameters
        ----------
        eval_file_path : str
            Path to evaluation file
        plant_id : int
            Plant ID
        plant_name : str
            Plant name (sheet name)
        curr_date : datetime
            Current date

        Returns
        -------
        bool
            True if successful
        """
        try:
            logging.info(f"Updating sheet for plant: {plant_name}")

            # Get measurements for plant
            start_of_month = curr_date.replace(day=1)
            start_date = start_of_month.date()

            measurements = self.db_manager.get_measurements_by_plant_and_date_eager(
                plant_id, start_date
            )

            if not measurements:
                logging.warning(
                    f"No measurements found for plant {plant_name} from {start_date}"
                )
                return False

            # Create dataframe from measurements
            meas_data = []
            for m in measurements:
                meas_data.append(
                    {
                        "data": m.date,
                        "timp": m.interval,
                        "productionmw": m.prod_val,
                        "forecastmw": m.forecast_val,
                    }
                )

            dfMeas = pd.DataFrame(meas_data)

            # Get imbalance prices for all dates
            all_dates = dfMeas["data"].unique()
            df_prices = self._get_imbalance_prices(all_dates, start_date)

            # Merge measurements with prices
            dfAll = pd.merge(dfMeas, df_prices, on=["data", "timp"], how="outer")
            dfAll = dfAll.sort_values(by=["data", "timp"])

            # Keep only current month data
            current_month_str = curr_date.strftime("%Y-%m")
            dfAll = dfAll[dfAll["data"].astype(str).str.startswith(current_month_str)]

            # Write data to sheet
            self._write_data_to_sheet(eval_file_path, plant_name, dfAll)

            return True

        except Exception as e:
            logging.error(f"Error updating plant sheet {plant_name}: {e}", exc_info=True)
            return False

    def _get_imbalance_prices(self, dates: List, start_date) -> pd.DataFrame:
        """Get imbalance prices for given dates.

        Parameters
        ----------
        dates : List
            List of dates
        start_date : date
            Start date filter

        Returns
        -------
        pd.DataFrame
            DataFrame with prices
        """
        try:
            prices = self.db_manager.get_all_imbalance_prices()

            if not prices:
                return pd.DataFrame(columns=["data", "timp", "positive_price", "negative_price"])

            price_data = []
            for price in prices:
                price_data.append(
                    {
                        "data": price.date,
                        "timp": price.interval,
                        "positive_price": price.positive_price,
                        "negative_price": price.negative_price,
                    }
                )

            df_prices = pd.DataFrame(price_data)
            df_prices = df_prices[df_prices["data"] >= start_date]

            return df_prices
        except Exception as e:
            logging.error(f"Error getting imbalance prices: {e}")
            return pd.DataFrame(
                columns=["data", "timp", "positive_price", "negative_price"]
            )

    def _write_data_to_sheet(
        self, file_name: str, sheet_name: str, df_all: pd.DataFrame
    ) -> bool:
        """Write measurement and price data to Excel sheet.

        Parameters
        ----------
        file_name : str
            Excel file path
        sheet_name : str
            Sheet name
        df_all : pd.DataFrame
            DataFrame with data to write

        Returns
        -------
        bool
            True if successful
        """
        try:
            workbook = load_workbook(file_name)

            if sheet_name not in workbook.sheetnames:
                logging.warning(f"Sheet {sheet_name} not found in workbook")
                return False

            sheet = workbook[sheet_name]
            start_row = 4  # Assuming data starts at row 4

            while (
                sheet.cell(row=start_row, column=1).value is not None
                and str(sheet.cell(row=start_row, column=1).value).strip() != "TOTAL LUNA"
                and start_row < 3000
            ):
                # Get date and time from sheet
                data = sheet.cell(row=start_row, column=1).value
                timp_cell = sheet.cell(row=start_row, column=2).value

                if not data or not timp_cell:
                    start_row += 1
                    continue

                timp = str(timp_cell)[:5]  # HH:MM format

                # Find matching row in dataframe
                matching_rows = df_all[
                    (df_all["data"].astype(str) == str(data))
                    & (df_all["timp"] == timp)
                ]

                if not matching_rows.empty:
                    row_data = matching_rows.iloc[0]

                    # Write production
                    prod_val = row_data.get("productionmw")
                    if prod_val is not None and prod_val != sheet.cell(
                        row=start_row, column=3
                    ).value:
                        sheet.cell(row=start_row, column=3, value=prod_val)

                    # Write forecast
                    fcst_val = row_data.get("forecastmw")
                    if fcst_val is not None and fcst_val != sheet.cell(
                        row=start_row, column=6
                    ).value:
                        sheet.cell(row=start_row, column=6, value=fcst_val)

                    # Write positive price
                    pos_price = row_data.get("positive_price")
                    if (
                        pos_price is not None
                        and pos_price != sheet.cell(row=start_row, column=9).value
                    ):
                        sheet.cell(row=start_row, column=9, value=pos_price)

                    # Write negative price
                    neg_price = row_data.get("negative_price")
                    if (
                        neg_price is not None
                        and neg_price != sheet.cell(row=start_row, column=10).value
                    ):
                        sheet.cell(row=start_row, column=10, value=neg_price)

                start_row += 1

            workbook.save(file_name)
            logging.info(f"Successfully updated sheet {sheet_name}")
            return True

        except Exception as e:
            logging.error(f"Error writing data to sheet: {e}", exc_info=True)
            return False
