import quopri
import psycopg2 as pg
import re
import os
os.chdir('/home/mohamed/git/basic_assembler_SQL/')
login = open('login.txt').read()

# Path to the .asm file
file_name = "test.asm"

conn = pg.connect(login)
cur = conn.cursor()

asm = open(file_name).readlines()
inputs = ''
for line in asm:

	if 'END' in line:
		break

	if line == '\n':
		continue

	# Remove comments
	line = re.sub('/[a-zA-Z ]+?$','',line)

	# Pad the input with 'NULL's to fit to table schema
	line = line.split()
	# non-memory-reference, or memory reference with no label or memory reference with no label but indirect
	if len(line) == 1 or (len(line) == 2 or len(line) == 3) and ',' not in line[0]:
		line.insert(0,'NULL')
	# non-memory-reference instructions
	if len(line) == 2:
		line.insert(2,'NULL')
	# check for indirect bit
	if len(line) == 4 and line[-1] == 'I':
		line[-1] = True
	else:
		line.append(False)

	inputs += str(tuple(line)) + ','

script = f'''
CREATE OR REPLACE FUNCTION raise_exception(text)
RETURNS void
language plpgsql
AS $$
BEGIN
	RAISE EXCEPTION '%', $1;
END $$;

CREATE TABLE IF NOT EXISTS errors(
row_no INTEGER
);

CREATE TABLE IF NOT EXISTS asm (
row_no SERIAL,
location VARCHAR(3),
variable VARCHAR(4) DEFAULT NULL,
command VARCHAR(3) NOT NULL,
result VARCHAR(4),
operand VARCHAR(4), 
indirect BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS nmr_ins (
command VARCHAR(3),
hexcode VARCHAR(4)
);

CREATE TABLE IF NOT EXISTS mr_ins (
command VARCHAR(3),
indirect BOOLEAN,
hexcode VARCHAR(1)
);

DELETE FROM asm;
DELETE FROM mr_ins;
DELETE FROM nmr_ins;
DELETE FROM errors;

-- start the SERIAL row_no column from 1 every time instead of dropping the table each run
ALTER SEQUENCE asm_row_no_seq RESTART WITH 1;

INSERT INTO nmr_ins VALUES 
('CLA', 7800 ),
('CLE', 7400 ),
('CMA', 7200 ),
('CME', 7100 ),
('CIR', 7080 ),
('CIL', 7040 ),
('INC', 7020 ),
('SPA', 7010 ),
('SNA', 7008 ),
('SZA', 7004 ),
('SZE', 7002 ),
('HLT', 7001 ),
('INP','F800'),
('OUT','F400'),
('SKI','F200'),
('SKO','F100'),
('ION','F080'),
('IOF','F040');

INSERT INTO mr_ins VALUES
('AND',FALSE, 0 ),
('AND',TRUE,  8 ),
('ADD',FALSE, 1 ),
('ADD',TRUE,  9 ),
('LDA',FALSE, 2 ),
('LDA',TRUE, 'A'),
('STA',FALSE, 3 ),
('STA',TRUE, 'B'),
('BUN',FALSE, 4 ),
('BUN',TRUE, 'C'),
('BSA',FALSE, 5 ),
('BSA',TRUE, 'D'),
('ISZ',FALSE, 6 ),
('ISZ',TRUE, 'E');

-- Insert the assembly code here
INSERT INTO asm(variable, command, operand,indirect) VALUES 
{inputs[:-1]}
;

DO $$
BEGIN
IF (SELECT command FROM asm WHERE row_no = 1) != 'ORG' THEN 
	SELECT raise_exception('Need an ORG command in line 1');
END IF;
END $$;

-- First pass (ORG, store values of variables)
-- While loop to execute the ORG commands
DO $$
DECLARE
to_start INTEGER:= (SELECT DISTINCT ON(command) row_no 
		FROM asm 
		WHERE command = 'ORG');

BEGIN WHILE (SELECT COUNT (*) FROM asm WHERE command = 'ORG') > 0 LOOP

-- change operand of ORG to binary then int then back to hex
UPDATE asm SET location = 
			LPAD(
				UPPER(
					TO_HEX(
						(SELECT ('x' || LPAD(operand,4,'0'))::bit(16)
						FROM asm 
						WHERE row_no = to_start)
						::INT + row_no - (1 + to_start)
						)
					)
			,3,'0')
		WHERE row_no > to_start;

DELETE FROM asm WHERE row_no = to_start;

to_start := (SELECT DISTINCT ON(command) row_no
		FROM asm 
		WHERE command = 'ORG');
 END LOOP;
END $$;

-- Replace the variables with decimals with their hexvalues 
UPDATE asm SET result = (
			CASE WHEN substring(operand,1,1) = '-' 
				THEN UPPER(
					substring(
						to_hex( ~substring(operand,2) ::INT - 1)
						,5)
						)
			ELSE 
				UPPER( LPAD( to_hex(operand::INT) ,4,'0') )
			END)
WHERE command = 'DEC';

-- Place the hexvalues directly inplace of variables
UPDATE asm 
SET result = UPPER(LPAD(operand,4,'0')) 
WHERE command = 'HEX';

-- Second pass
-- Replace operands with variables, memory reference and non-memory reference instructions with their hexcodes
UPDATE asm a 
SET operand = b.location 
FROM asm b 
WHERE a.operand || ',' = b.variable;

UPDATE asm a 
SET result = b.hexcode 
FROM nmr_ins b 
WHERE a.command = b.command;

UPDATE asm a 
SET result = b.hexcode||a.operand 
FROM mr_ins b 
WHERE a.command = b.command and a.indirect = b.indirect;

-- command written is not a pseudo-instruction,memory-reference nor non-memory-reference instruction,
-- raise an error later
INSERT INTO errors(row_no) SELECT row_no FROM asm WHERE result IS NULL;

-- Create a view to show the final results in hexadecimals
CREATE OR REPLACE VIEW hexresult AS
SELECT location, result
from asm 
ORDER BY row_no;

-- Create a view to show the final results in binary
CREATE OR REPLACE VIEW binresult AS
SELECT ('x' || lpad(location::text,4,'0'))::bit(16) AS location,
('x'||result)::bit(16) AS command
FROM asm 
ORDER BY row_no;
'''

try:
	cur.execute (script)
except:
	# Raise exception when any of the length constraints in the asm table are broken
	# or when ORG is missing from the top of the file
	print(
	'''The assembler has encountered an error.
	Please make sure that the input file follows the rules of the assembly language!
	This Error was likely caused by a missing ORG pseudo-instruction at the top of the program
	or broken length constraints!''')
	quit()

# Write the binary result to a text file
handle = open(f"{file_name.split('.')[0]}"+'.mc','w+')

cur.execute('SELECT * FROM errors;')
errors = cur.fetchall()
if errors:
	raise(Exception(f'Wrong command(s) in line(s): {sorted([i[0] for i in errors])}'))

cur.execute('SELECT * FROM hexresult;')
print('\nResults in Hexadecimal:\n')
for result in cur.fetchall():
	print(result)
  
cur.execute('SELECT * FROM binresult;')
print('\nResults in Binary:\n')
for result in cur.fetchall():
	handle.write('\t'.join(result)+'\n')
	print(result)

cur.close()
conn.commit()