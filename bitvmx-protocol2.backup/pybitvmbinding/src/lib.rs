#[allow(dead_code)]
// Re-export what is needed to write treepp scripts
pub mod treepp {
    pub use bitcoin_script::{script, Script};
}

use pyo3::prelude::*;
use crate::treepp::*;
use bitvm::hash::sha256_u4::*;
use bitvm::u4::{u4_add::*, u4_logic::*, u4_rot::*, u4_std::*};
use bitvm::{execute_script};

/// A Python module implemented in Rust.
#[pymodule]
fn pybitvmbinding(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(return_complex_script, m)?)?;
    m.add_function(wrap_pyfunction!(sha_256_script, m)?)?;
    m.add_function(wrap_pyfunction!(execute_sha_256_script, m)?)?;
    Ok(())
}

#[pyfunction]
pub fn return_complex_script() -> PyResult<Vec<u8>> {
    let script = script! {
        { u4_number_to_nibble(0xdeadbeaf) }
        { u4_number_to_nibble(0x01020304) }
        { sha256(8) }
        { u4_drop(64) }
        OP_TRUE
    };
    Ok(script.compile().into_bytes())
    //Ok(script)
}

#[pyfunction]
pub fn sha_256_script(size: u32) -> PyResult<Vec<u8>> {
    let script = script! {
        { sha256(size) }
    };
    Ok(script.compile().into_bytes())
    //Ok(script)
}

#[pyfunction]
pub fn execute_sha_256_script() -> PyResult<bool> {
    let input_array: Vec<u8> = vec![0x0d, 0x0e, 0x0a, 0x0d, 0x0b, 0x0e, 0x0a, 0x0f];
    let sha_result: &str = "5065e21cfeeefbd68372c58166fa44ae8a6595cd4011f06c1b01623270dd0240";
    let converted_array: Vec<_> = sha_result.as_bytes()
        .chunks(1)
        .map(|chunk| {
            let pair = std::str::from_utf8(chunk).unwrap();
            u8::from_str_radix(pair, 16).map_err(|_| "Invalid hex digit")
        })
        .collect();
    let script = script! {
        //{ u4_number_to_nibble(0xdeadbeaf) }
        // 5065e21cfeeefbd68372c58166fa44ae8a6595cd4011f06c1b01623270dd0240
        for value in input_array.iter() {
            { *value }
        }
        { sha256(4) }
        for elem in converted_array.iter().rev() {
            { elem.unwrap() }
            OP_EQUALVERIFY
        }
        OP_TRUE
    };
    let res = execute_script(script);
    Ok(res.success)
}


mod test {
    use crate::treepp::*;
    use bitvm::execute_script;
    use crate::{execute_sha_256_script, sha_256_script};

    #[test]
    fn test_print_vec() {

    }

    #[test]
    fn test_execute_sha_256_script() {
        let result = execute_sha_256_script();
        assert!(result.unwrap())
    }

    #[test]
    fn test_sha_256_script() {
        let input_str: &str = "deadbeaf";
        let converted_input_array: Vec<_> = input_str.as_bytes()
            .chunks(1)
            .map(|chunk| {
                let pair = std::str::from_utf8(chunk).unwrap();
                u8::from_str_radix(pair, 16).map_err(|_| "Invalid hex digit")
            })
            .collect();

        let script_hex = sha_256_script(converted_input_array.len() as u32 / 2);
        let sha_256_script = Script::from_bytes(script_hex.unwrap());

        let sha_result: &str = "5065e21cfeeefbd68372c58166fa44ae8a6595cd4011f06c1b01623270dd0240";
        let converted_result_array: Vec<_> = sha_result.as_bytes()
            .chunks(1)
            .map(|chunk| {
                let pair = std::str::from_utf8(chunk).unwrap();
                u8::from_str_radix(pair, 16).map_err(|_| "Invalid hex digit")
            })
            .collect();

        let script_with_test = script! {
            for value in converted_input_array.iter() {
                { value.unwrap() }
            }
            { sha_256_script }
            for elem in converted_result_array.iter().rev() {
                { elem.unwrap() }
                OP_EQUALVERIFY
            }
            OP_TRUE
        };

        let result = execute_script(script_with_test);
        assert!(result.success)
    }

    #[test]
    fn test_sha_256_script_2() {
        let input_str: &str = "81084ca68bad5161f4a05599828cdc8d";
        let converted_input_array: Vec<_> = input_str.as_bytes()
            .chunks(1)
            .map(|chunk| {
                let pair = std::str::from_utf8(chunk).unwrap();
                u8::from_str_radix(pair, 16).map_err(|_| "Invalid hex digit")
            })
            .collect();

        let script_hex = sha_256_script(converted_input_array.len() as u32 / 2);
        let sha_256_script = Script::from_bytes(script_hex.unwrap());

        let sha_result: &str = "ca1bc4b0fac1ad0157593eb3a06e4bae40ca7f581b0d10faeaa5b226721c831c";
        let converted_result_array: Vec<_> = sha_result.as_bytes()
            .chunks(1)
            .map(|chunk| {
                let pair = std::str::from_utf8(chunk).unwrap();
                u8::from_str_radix(pair, 16).map_err(|_| "Invalid hex digit")
            })
            .collect();

        let script_with_test = script! {
            for value in converted_input_array.iter() {
                { value.unwrap() }
            }
            { sha_256_script }
            for elem in converted_result_array.iter().rev() {
                { elem.unwrap() }
                OP_EQUALVERIFY
            }
            OP_TRUE
        };

        let result = execute_script(script_with_test);
        assert!(result.success)
    }
}