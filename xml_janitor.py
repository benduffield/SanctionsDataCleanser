import logging
import pandas as pd
import xmlschema
from lxml import etree
import sys

#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#Logging configurations
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

general_handler = logging.FileHandler("logging.log", mode="w")
general_handler.setLevel(logging.INFO)
general_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(general_handler)

missing_handler = logging.FileHandler("missing_data.log", mode="w")
missing_handler.setLevel(logging.WARNING)
general_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(missing_handler)

#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#Validating xml file against schema
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

#build schema object
def build_schema_object(xsd_path):
    try:
        schema_object = xmlschema.XMLSchema(xsd_path) #Build an XMLSchema object
        logger.info("Succesfully built schema")
        return schema_object
    except:
        logger.error("Failed to build schema") #Catch and log an error if schema fails to build
        return None

#validate xml against schema
def validate_xml(xml_path, schema_object):
    try:
        schema_object.validate(xml_path) #Check provided xml against schema.
        logger.info("Validated XML against schema")
        return True

    except xmlschema.XMLSchemaValidationError as e: #Catch and log validation errors
        logger.error(f"Validation failed: {e.message}")
        return False

    except Exception as e:
        logger.error(f"Error: {e.message}") #Catch and log other errors
        return False

#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#Get list of needed designations
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

#Function for obtaining list of designations. Takes input of the root of an etree object.
def get_designations(tree):
    des_list = [child for child in tree.iterchildren() if child.tag != "DateGenerated"]
    logger.info("Retrieved designations")
    return des_list

#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#Janitors for extracting and cleaning relevant data
#Each function takes an element/tree, finds the relevant data using xml tags and xpaths,
#cleans + formats the data,
#returns cleaned data.
#Each janitor begins with is None to ensure proper spacing when converting to a csv file if no data is found.
#Results are stored in sets instead of lists to ensure no duplicate entries unless order needs to be preserved,
#in which case if else statements are used to check if the value already exists within a list.
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

#Fetch unique ID from a designation
def uniqueid_janitor(UniqueID):
    if UniqueID is None:
        #Raise a warning if no Unique ID is found, but proceed with None
        logger.warning("Failed to find unique ID")
        return None

    logger.info(f"Found unique ID: {UniqueID.text}")
    return UniqueID.text.strip()

#Fetch and clean titles from a designation
def title_janitor(Titles, uniqueID):
    if Titles is None:
        logger.warning(f"No titles found for {uniqueID}")
        return None

    res = set()
    for child in Titles.iterchildren():
        res.add(child.text.lower().strip())
    logger.info(f"Found titles for {uniqueID}")
    return " | ".join(list(res))

#Fetch and validate designation type
def designation_type_janitor(des_type, uniqueID):
    cleaned_des_type = des_type.lower().strip()

    #Check if des type is valid as per government website rules
    if cleaned_des_type in ["individual", "entity", "ship"]:
        logger.info(f"Found designation type for {uniqueID}")
        return cleaned_des_type

    #If des type is not IndividualEntityShip, raise a warning but still proceed with unknown type.
    else:
        logger.warning(f"Unexpected designation type for {uniqueID}: {des_type}")
        return des_type

#Gather and clean latin names
def latin_name_janitor(Names, uniqueID):
    if Names is None:
        logger.warning(f"No names found for {uniqueID}")
        return None

    #Initialise as lists to preserve order
    primary_name = []
    secondary_names = []

    #Iterate over each name in the Names tag
    for name in Names.iterchildren():

        #Gather and normalise each element under the name tree, ensuring order is kept
        namelist = [name.findtext(f"Name{i}") for i in range(1, 7)]
        fullname = " ".join([namex.lower().strip() for namex in namelist if namex != None])
        nametype = name.findtext(".//NameType").lower().strip()

        #If else to seperate primary name from secondary names. Primary names with other strenghts are included in
        #secondary names
        if nametype == "primary name":
            primary_name.append(fullname)
            logger.info(f"Found primary name for {uniqueID}")
        else:
            secondary_names.append(fullname)
    return [primary_name[0], " | ".join(secondary_names)]

#Fetch and clean non latin names.
def non_latin_name_janitor(NonLatinNames, uniqueID):
    if NonLatinNames is None:
        logger.warning(f"No non latin names found for {uniqueID}")
        return None

    nameset = set()
    for name in NonLatinNames.iterdescendants():
        if name.tag == "NameNonLatinScript":
            cleaned_name = " ".join(name.text.split())
            nameset.add(cleaned_name)
    logger.info(f"Found non latin names for {uniqueID}")
    return list(nameset)

#Fetch and encode genders
def gender_janitor(Genders, uniqueID):
    if Genders is None:
        logger.warning(f"No genders found for {uniqueID}")
        return None

    res = set()
    for child in Genders.iterchildren():
        if child.tag == "Gender":
            gender = child.text.lower().strip()

            #Encode male to m and female to f for more structure and standardisation
            gender_code = "m" if gender == "male" else "f" if gender == "female" else gender
            res.add(gender_code)
    logger.info(f"Found gender for {uniqueID}")
    return " | ".join(list(res))

#Fetch and standardise dates of birth
def dob_janitor(DOBs, uniqueID):
    if DOBs is None:
        logger.warning(f"No DOB found for {uniqueID}")
        return None

    DOBset = set()
    for DOB in DOBs.iterchildren():
        DOBtext = DOB.text

        #Check if DOB is formatted as yyyy or dd/mm/yyyy and proceed accordingly
        if len(DOBtext) > 3 and DOBtext.isdigit():
            DOBset.add(f"dd/mm/{DOBtext}")
        else:
            DOBset.add(DOBtext)
    logger.info(f"Added DOB(s) for {uniqueID}")
    return " | ".join(list(DOBset))

#Find and standardise birth country
def birth_country_janitor(CountryOfBirth, uniqueID):
    if CountryOfBirth is None:
        logger.warning(f"No birth country found for {uniqueID}")
        return None
    logger.info(f"Found country for {uniqueID}")
    return CountryOfBirth.text.lower().strip()

#Find and standardise address(s)
def address_janitor(Addresses, uniqueID):
    if Addresses is None:
        logger.warning(f"No addresses found for {uniqueID}")
        return None

    res = set()
    for Address in Addresses.iterchildren():

        #Loop through Address1 - Address6, and add the post code and country
        addresslist = [Address.findtext(f"AddressLine{i}") for i in range(1, 7)]
        addresslist.append(Address.findtext("AddressPostalCode"))
        addresslist.append(Address.findtext("AddressCountry"))

        fulladdress = ", ".join([add.lower().strip() for add in addresslist if add != None])
        res.add(fulladdress)
    logger.info(f"Found address(s) for {uniqueID}")
    return " | ".join(list(res))

#Find passport number
#I left passport number as is since different countries may have different formats for passport numbers,
#So i decided to preserve the integrity of the data.
def passport_no_janitor(PassportDetails, uniqueID):
    if PassportDetails is None:
        logger.warning(f"No passport details found for {uniqueID}")
        return None

    res = set()
    for Passport in PassportDetails.iterdescendants():
        if Passport.tag == "PassportNumber":
            res.add(Passport.text)
    logger.info(f"Found passport details for {uniqueID}")
    return " | ".join(list(res))

#Find and standardise phone numbers.
def phone_number_janitor(PhoneNumbers, uniqueID):
    if PhoneNumbers is None:
        logger.warning(f"No phone numbers found for {uniqueID}")
        return None

    res = set()
    for child in PhoneNumbers.iterchildren():

        #Ensure all phone numbers are consistent with each other by removing any dashes,
        #Allowing for easier and more universal searching
        num = child.text.split("-")
        cleaned_num = "".join([num.lower().strip() for num in num if num != "-"])
        res.add(cleaned_num)
    logger.info(f"Found phone number(s) for {uniqueID}")
    return " | ".join(list(res))

#Find email addresses
def email_address_janitor(EmailAddresses, uniqueID):
    if EmailAddresses is None:
        logger.warning(f"No email addresses found for {uniqueID}")
        return None

    res = set()
    for child in EmailAddresses.iterchildren():
        email = child.text.strip()
        res.add(email)
    logger.info(f"Found email address(s) for {uniqueID}")
    return " | ".join(list(res))

#Find IMO number for ships
def imonum_janitor(IMONumber, uniqueID):
    if IMONumber is None:
        logger.warning(f"No IMO Number found for {uniqueID}")
        return None

    imo_num = IMONumber.text.strip()

    #Ensure all IMO numbers are proceeded with IMO
    if imo_num.isdigit():
        return f"IMO{imo_num}"
    else:
        return imo_num

#Fetch all current and previous owners of the ship
#Formatting is as follows: Current owner(s) || Previous Owner(s)
#This means more information is given in the final csv file whilst still maintaining searchability
def ship_owner_janitor(Ship, uniqueID):
    if Ship is None:
        logger.warning(f"No ship owner found for {uniqueID}")
        return None

    current_owners = set()
    previous_owners = set()

    #Split current and previous owners
    for child in Ship.iterdescendants():
        if child.tag == "CurrentOwnerOperator":
            cleaned_name = child.text.lower().strip().split()
            current_owners.add(" ".join(cleaned_name))
        elif child.tag == "PreviousOwnerOperator":
            cleaned_name = child.text.lower().strip().split()
            previous_owners.add(" ".join(cleaned_name))

    logger.info(f"Found ship owner(s) for {uniqueID}")

    #Logic for joining two strings with a double pipe if there exist secondary owners
    current_str = " | ".join(current_owners)
    previous_str = " | ".join(previous_owners)
    final_list = (current_str + " || " + previous_str if previous_owners else current_str)
    return final_list

#Find all current and previous flags for a ship.
#Formatting is as follows: Current flag || Previous flag(s)
def flag_janitor(Ship, uniqueID):
    if Ship is None:
        logger.warning(f"No ship flag found for {uniqueID}")
        return None

    current_flags = set()
    previous_flags = set()

    for child in Ship.iterdescendants():
        if child.tag == "CurrentBelievedFlagOfShip":
            cleaned_name = child.text.lower().strip().split()
            current_flags.add(" ".join(cleaned_name))
        elif child.tag == "PreviousFlag":
            cleaned_name = child.text.lower().strip().split()
            previous_flags.add(" ".join(cleaned_name))

    logger.info(f"Found ship flag(s) for {uniqueID}")

    #Logic for splitting current and previous flags
    current_str = " | ".join(current_flags)
    previous_str = " | ".join(previous_flags)
    final_list = (current_str + " || " + previous_str if previous_flags else current_str)
    return final_list

#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#Build csv file
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

#Set columns for csv
columns = ["Unique ID",
           "Title(s)",
           "Primary Name",
           "Secondary Name(s)",
           "Designation Type",
           "Non-Latin Name(s)",
           "Gender",
           "DOB(s)",
           "Birth Country",
           "Address(s)",
           "Passport Number(s)",
           "Phone number(s)",
           "Email Address(s)",
           "IMO number",
           "Owners (present and past)",
           "Associated flags (present and past)"]

#Function to build and save the csv file
def build_csv(designations):
    df_data = [columns]
    for designation in designations:

        #Create output list for storing needed data about each Unique ID
        output_list = []

        #Find xpaths to needed elements/subtree and run janitor on data
        uniqueid = designation.find(".//UniqueID")
        clean_uniqueid = uniqueid_janitor(uniqueid)
        output_list.append(clean_uniqueid)

        titles = designation.find(".//Titles")
        output_list.append(title_janitor(titles, clean_uniqueid))

        names = designation.find(".//Names")
        primary, secondary = latin_name_janitor(names, clean_uniqueid)
        output_list.append(primary)
        output_list.append(secondary)

        des_type = designation.findtext(".//IndividualEntityShip")
        output_list.append(designation_type_janitor(des_type, clean_uniqueid))

        non_latin = designation.find(".//NonLatinNames")
        output_list.append(non_latin_name_janitor(non_latin, clean_uniqueid))

        gender_block = designation.find(".//Genders")
        output_list.append(gender_janitor(gender_block, clean_uniqueid))

        dob_block = designation.find(".//DOBs")
        output_list.append(dob_janitor(dob_block, clean_uniqueid))

        birth_country = designation.find(".//CountryOfBirth")
        output_list.append(birth_country_janitor(birth_country, clean_uniqueid))

        address_block = designation.find(".//Addresses")
        output_list.append(address_janitor(address_block, clean_uniqueid))

        passport_block = designation.find(".//PassportDetails")
        output_list.append(passport_no_janitor(passport_block, clean_uniqueid))

        phone_number_block = designation.find(".//PhoneNumbers")
        output_list.append(phone_number_janitor(phone_number_block, clean_uniqueid))

        email_address_block = designation.find(".//EmailAddresses")
        output_list.append(email_address_janitor(email_address_block, clean_uniqueid))

        imo_num_block = designation.find(".//IMONumber")
        output_list.append(imonum_janitor(imo_num_block, clean_uniqueid))

        ship_block = designation.find(".//Ship")
        output_list.append(ship_owner_janitor(ship_block, clean_uniqueid))
        output_list.append(flag_janitor(ship_block, clean_uniqueid))

        df_data.append(output_list)

    #Create dataframe and save to a csv file
    df = pd.DataFrame(df_data)
    logger.info('Created dataframe')
    clean_csv_path = "./CleanedSanctionsData.csv"
    df.to_csv(clean_csv_path, index=False)
    logger.info(f"Saved cleaned csv to {clean_csv_path}")

#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#Main method to run functions in correct order
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

def main(xml_path, xsd_path):
    logger.info('Started')
    xmltree = etree.parse(xml_path)
    root = xmltree.getroot()
    schema = build_schema_object(xsd_path)
    validate_xml(xml_path, schema)
    designations = get_designations(root)
    build_csv(designations)
    logger.info('Finished')

#Collect xml and xsd paths as input from user
if __name__ == "__main__":
    xml_path = sys.argv[1]
    xsd_path = sys.argv[2]
    main(xml_path, xsd_path)
