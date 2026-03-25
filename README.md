# Scan Gogh - QR Code Generator & Reader

> A high-fidelity QR code engine built from scratch, capable of encoding strings into visual matrices and decoding images back into data. Named in honor of the art of encoding.

**Authors & Contributors:** 
* **Răzvan** - [@GabreanuR](https://github.com/GabreanuR)
* **Maia** - [@maia-sapunaru](https://github.com/maia-sapunaru)
* **Ruxi** - [@rmig22](https://github.com/rmig22)

---

## Project Overview

**Scan Gogh** is a Python-based system that handles the complete lifecycle of a QR code. Unlike simple wrappers, this project implements the core logic of the QR standard, including Reed-Solomon error correction, mask optimization, and zig-zag bit extraction.

---

## Technical Workflow

### 1. The Art of Generation (Encoding)
The transformation from a raw string to a printable PNG follows a strict 11-step pipeline:

1. **Bitstream Conversion:** Input strings are converted into binary sequences.
2. **Padding:** Application of initial and final sequences to meet standard length requirements.
3. **Data Blocking:** Segregating the binary stream into blocks based on version capacity.
4. **Error Correction (ECC):** Implementing **Reed-Solomon** codes to ensure data integrity even if the code is partially damaged.
5. **Structural Mapping:** Rearranging bits to fit the physical QR architecture.
6. **Matrix Initialization:** Creating a grid of `0`s and `1`s (binary representation of modules).
7. **Reserved Patterns:** Placing position detection patterns (large squares), timing lines, and alignment markers.
8. **Data Placement:** Inserting the bitstream into the available matrix space.
9. **Masking & Optimization:** Applying all 8 standard QR masks. The system evaluates each outcome against penalty rules to select the mask with the least visual noise.
10. **Final Formatting:** Applying format and version information bits.
11. **Image Rendering:** Converting the mathematical matrix into a high-resolution **PNG** file using the Pillow library.

### 2. The Art of Reading (Decoding)
To retrieve the data, the system reverses the encoding logic through image processing:

* **Binarization:** Resizing the input image and converting pixels into a clean `0/1` matrix.
* **Metadata Extraction:** Reading the format bits to identify which of the 8 masks was used.
* **De-masking:** Reversing the XOR operation to reveal the underlying data.
* **Zig-Zag Traversal:** Extracting bits in the specific non-linear order required by the QR standard.
* **Binary Decoding:** Converting the extracted sequence back into a human-readable string.

---

## Tech Stack & Libraries
* **Python 3**
* **Pillow (PIL):** Used for matrix-to-image conversion and pixel-level analysis.
* **NumPy:** For efficient matrix manipulations.
* **ReedSolo:** To handle complex Error Correction Code (ECC) logic.

---

## Getting Started

### Prerequisites
Ensure you have Python 3 installed. Clone the repository and install the required dependencies:

```bash
git clone [https://github.com/GabreanuR/Scan-Gogh.git](https://github.com/GabreanuR/Scan-Gogh.git)
cd Scan-Gogh
pip install -r requirements.txt
```

### Running the Application
The system features an interactive Command Line Interface (CLI). Start the engine by running:

```bash
python main.py
```

## 📂 Project Architecture

The codebase is fully modularized, adhering to Software Engineering principles (Separation of Concerns, DRY):

* `main.py` - The CLI orchestrator and entry point.
* `encoder.py` - Core logic for generating, error-correcting, and masking QR matrices.
* `decoder.py` - Image processing, de-masking, and bitstream decoding.
* `utils.py` - Shared utilities (image scaling, reserved pattern detection).
* `config.py` - Centralized ISO standard constants (BCH polynomials, alignment coordinates, capacities).

---

## Demo & Documentation
Watch the system in action and see a detailed walkthrough of the implementation:  
[**Project Video Explanation**](https://www.youtube.com/watch?v=NIO0ZfSSZ34)

---

## References & Resources

### Core Logic
* [Creating a QR Code Step-by-Step](https://www.nayuki.io/page/creating-a-qr-code-step-by-step) - The primary guide for this implementation.
* [QR Code Tutorial: Format & Version](https://www.thonky.com/qr-code-tutorial/format-version-information)

### ECC & Data Structures
* [Reed-Solomon Codec Documentation](https://pypi.org/project/reedsolo/)
* [Timing & Alignment Patterns Analysis](https://www.youtube.com/watch?v=pamazHwk0hg)

### Image Processing
* [Pillow: Binary Matrix to PNG](https://stackoverflow.com/questions/78913551/python-using-pillow-to-convert-any-format-to-png)
* [RGB Pixel Value Extraction Guide](https://stackoverflow.com/questions/138250/how-to-read-the-rgb-value-of-a-given-pixel-in-python)