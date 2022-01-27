# Description

This is an assembler written for the basic computer proposed by Morris Mano in his Computer Systems Architecture textbook. The asssembler is written in SQL with some python for easier string manipulation (removing .asm comments and preparing code for insertion in database) and for providing an interface to show the output or the machine code. The code is written for PostgreSQL and therefore uses PL/pgsql. This is why psycopg2 is used for the project. 

I built the same project using bash again as a practice [here](https://github.com/MohamedAbdeen21/basic_assembler_bash).

## Database setup

If you don't have postgreSQL installed on your machine you can create a free database using https://customer.elephantsql.com/login. Once you create an instance, you will be provided by the required login credentials. 
