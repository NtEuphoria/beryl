#ifndef BERYL_DOCTOR_H
#define BERYL_DOCTOR_H
/* Inventory is read-only. Only an explicit native probe creates owned files
 * and launches the selected C compiler and a fixed diagnostic executable. */
int doctor_command(int argc, char **argv, const char *compiler_version);
#endif
