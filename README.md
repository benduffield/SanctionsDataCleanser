# Data cleansing assignment

The goal of this assignment was to take raw data of individuals sanctioned by the UK Government and clean + process the data into a structured dataset suitable for matching against customer records of a bank.

This document aims to provide information as to how to run the cleanser, as well as insights about the quality of data.

## Running the code:

Dependencies:

* pandas 
  * Building the cleaned + processed dataframe, as well as exporting to csv.
  
  ```
  pip install pandas
  ```
* xmlschema
  * Creating etree objects for parsing xml and element traversal.

  ```
  pip install xmlschema
  ```
* lxml
  * Creating the schema object and validating the xml input
  
  ```
  pip install xmlschema
  ```
  
How to run the cleanser once dependencies have been installed:

1. Download the "XML format UK Sanctions list" and the "UK Sanctions list schema" from https://www.gov.uk/government/publications/the-uk-sanctions-list
2. Run the xml_janitor.py file passing in two arguments:
   1. arg1 is the file path to the sanctions list (.\UK-Sanctions-List.xml)
   2. arg2 is the file path to the schema (.\SanctionsListSchema-4.33.3.xsd)

  ```
  python3 .\xml_janitor.py arg1 arg2
  ```
3. Output of interest will be in a csv format and will be named "CleanedSanctionsData.csv". Two more files "logging.log" and "missing_data.log" will also be made. The "logging.log" file contains logs of all log instances, whilst the "missing_data.log" logs every instance where no data is found for a particular designation.

The code checks three levels of correctness:

1. well-formed xml (fail fast)
2. valid xml against the schema definition (fail fast)
3. business rules (janitors) to cleanse the data (business rule failures)

## Insights:

Insights into the cleanliness of the original raw data.

### Formatting inconsistencies:

To give some context, I originally chose an xml format due to the presence of a schema. However, the schema provided by the UK Government has proven to be quite weak in terms of formatting consistency, often setting element types as string and having minoccurences = 0. As such I have created some of my own formatting detailed below.

* In the case where multiple values appear in one cell, I have seperated them by a pipe "|". In the subcase where order of the elements matters, for example in the "Owners (present and past)" column, current ownsers have been seperated from previous owners using a double pipe "||".
* Date of birth - some dates were given as yyyy, others as dd/mm/yyyy. As such, all dates are now formatted as dd/mm/yyyy.
* IMO numbers - Some IMO numbers included the IMO prefix whilst others did not. As such, all IMO numbers now begin with the prefix "IMO" followed by a 7 digit number.
* All names (Title, Primary Name, Secondary Name(s), Non-Latin Names, Birth Country, Address(s), Owners, Associated flags) are all in lower case and seperated by a single whitespace. This is for consistency, as some names were in all caps, whilst others had no capital letters.
* Phone numbers - all phone numbers are a single string of numbers unless brackets have been provided. This was because some phone numbers had dashes for easier reading, whilst others were formatted as one consistent string. All dashes have been removed.

### Duplicate records:

To handle duplicate records, I often used a set (instead of a list) to preserve uniqueness. In the case where order of the elements matter, if else statements were used. 

There is also a potential issue with duplicate records in non-latin names. For example, the name "John Smith" and "Johns Mith" will appear as two seperate names in the output csv. Since I am not familiar with non-latin scripts, I kept each of these occurences as to not lose data integrity. They have still been formatted and standardised using one white space between words. There is also of course the possibility that these are completely seperate names. Either way, I believe keeping hold of each variation will help with fuzzy matching.

### Missing or inconsistent fields:

There is a lot of missing data in the final csv output. This could be for two main reasons:

* Designation type - A designation of type Individual will not have any data about an IMO number, for example. This means that the cell is intentionally left blank.
* Lack of data - Data provided is often incomplete or missing completely. For example, date of birth may only provide the year of birth, or be missing from a designation entirely. In order to protect the integrity of the data, I have not tried to extrapolate any of the incomplete/missing fields.

## Enhancements

* To document missing data, I created a seperate log handler to write to an output file using only one logger. I understand this is a generic fix, and that more loggers and handlers can be used for more detailed and accurate logging.
* To validate and cleanse any other xml fields, simply add another janitor
* To further validate fields such as email addresses and phone numbers, regular expressions can be used to check data more vigorously