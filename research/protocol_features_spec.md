# Watchify Smart Features Protocol Specification

This document details the reverse-engineered payload structures for the "Smart Features" opcodes used by the generic ZK-based watch firmware, specifically derived from decompiled, unobfuscated Java source code (`extracted_java/sources/com/wtwd/utra/`).

## Opcode 106: Alarm Clock (`DATA_TYPE_ALARM_CLOCK`)

The watch supports syncing a list of alarms. The payload is sent as a single packet containing a header byte followed by a repeating 5-byte block for each alarm.

### Packet Structure
*   **Header:**
    *   `byte[0]`: Total count of alarms in the packet (`N`)

*   **Alarm Block (5 bytes, repeating `N` times):**
    For each alarm block `i` (where the block starts at offset `1 + (i * 5)`):
    *   `+0` (Type/ID): `byte` representing the alarm type or ID index.
    *   `+1` (Repeat Mask): `byte` representing the days of the week the alarm repeats.
        *   `127` (0x7F): Everyday
        *   Bitmask values: Monday (`1`), Tuesday (`2`), Wednesday (`4`), Thursday (`8`), Friday (`16`), Saturday (`32`), Sunday (`64`).
    *   `+2` (Hour): `byte` representing the hour (0-23 in 24-hour format).
    *   `+3` (Minute): `byte` representing the minute (0-59).
    *   `+4` (State): `byte` representing the enable/disable state (`1` for enabled, `0` for disabled).

## Opcode 135: Address Book / Contacts (`DATA_TYPE_ADDRESS_BOOK`)

The watch allows syncing an address book of contacts. Because contact lists can be large and exceed the standard MTU size, the protocol chunks the payload. No single payload chunk may exceed **220 bytes**.

### Packet Structure
Each chunked payload starts with a 2-byte header, followed by a dynamic-length block for each contact included in the chunk.

*   **Header (2 bytes):**
    *   `byte[0]`: `i3` - The 1-based index/sequence number of the current chunk batch.
    *   `byte[1]`: `i2` - The number of contacts contained within this specific chunk.

*   **Contact Block (Dynamic Length, repeating `i2` times):**
    For each contact:
    *   `byte`: `L1` (Length of the contact's name string in bytes).
    *   `byte[L1]`: The contact's name (UTF-8 encoded string).
    *   `byte`: `L2` (Length of the contact's phone number string in bytes).
    *   `byte[L2]`: The contact's phone number (ASCII encoded string, numbers only).

### Sync Flow
1. The app iterates through the list of contacts to sync.
2. It packs contacts into a byte array following the block structure above.
3. If adding the next contact would cause the payload size to exceed 220 bytes, the current payload is dispatched as a complete packet, the sequence number (`byte[0]`) is incremented, the contact count (`byte[1]`) is reset, and a new payload array is started.
4. The app waits for a `DeviceAnswerEvent` from the watch confirming receipt of Opcode 135 before dispatching the next chunk in the sequence.
