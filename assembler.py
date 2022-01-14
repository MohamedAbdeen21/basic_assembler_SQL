import psycopg2 as pg
import re

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
CREATE TABLE IF NOT EXISTS asm (
 row_no SERIAL,
 location VARCHAR(3),
 variable VARCHAR(4) DEFAULT NULL,
 command VARCHAR(4) NOT NULL,
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

-- First pass (ORG, store values of variables)
-- While loop to execute the ORG commands
DO $$
DECLARE
to_start INTEGER:= (SELECT DISTINCT ON(command) row_no 
		FROM asm 
		WHERE command = 'ORG');

BEGIN WHILE (SELECT COUNT (*) FROM asm WHERE command = 'ORG') > 0 LOOP

-- change operand of ORG to binary then int then back to hex
UPDATE asm SET location = UPPER(TO_HEX((SELECT ('x' || '0' || operand)::bit(16)
				FROM asm 
				WHERE row_no = to_start)
			::INT + row_no - (1 + to_start)))
			WHERE row_no > to_start;

DELETE FROM asm WHERE row_no = to_start;

to_start := (SELECT DISTINCT ON(command) row_no
		FROM asm 
		WHERE command = 'ORG');
 END LOOP;
END $$;

-- Replace the variables with decimals with their hexvalues 
UPDATE asm SET command = (
 CASE 
 WHEN substring(operand,1,1) = '-' THEN UPPER(substring(to_hex(~substring(operand,2)::INT::bit(16)::INT - 1),5))
ELSE 
	UPPER(LPAD(to_hex(operand::INT),4,'0'))
 END
 )
 WHERE command = 'DEC';

-- Place the hexvalues directly inplace of variables
UPDATE asm 
SET command = UPPER(LPAD(operand,4,'0')) 
WHERE command = 'HEX';

-- Second pass
-- Replace operands with variables, memory reference and non-memory reference instructions with their hexcodes
UPDATE asm a 
SET operand = b.location 
FROM asm b 
WHERE a.operand || ',' = b.variable;

UPDATE asm a 
SET command = b.hexcode 
FROM nmr_ins b 
WHERE a.command = b.command;

UPDATE asm a 
SET command = b.hexcode||a.operand 
FROM mr_ins b 
WHERE a.command = b.command and a.indirect = b.indirect;

-- Create a view to show the final results in hexadecimals
CREATE OR REPLACE VIEW hexresult AS
SELECT location, command
from asm 
ORDER BY row_no;

-- Create a view to show the final results in binary
CREATE OR REPLACE VIEW binresult AS
SELECT ('x' || lpad(location::text,4,'0'))::bit(16) AS location,
 ('x'||command)::bit(16) AS command
FROM asm 
ORDER BY row_no;
'''
cur.execute (script)

# Write the binary result to a text file
handle = open(f"{file_name.split('.')[0]}"+'.mc','w+')

cur.execute('SELECT * FROM hexresult;')
print('\nResults in Hexadecimal:\n')
for result in cur.fetchall():
	print(result)
  
cur.execute('SELECT * FROM binresult;')
print('\nResults in Binary:\n')
for result in cur.fetchall():
	handle.write("\t".join(result)+'\n')
	print(result)

cur.close()
conn.commit()