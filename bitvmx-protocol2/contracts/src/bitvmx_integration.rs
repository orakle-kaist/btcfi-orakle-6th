//! BitVMX 통합 모듈
//! 
//! RISC-V toolchain을 사용한 프로그램 컴파일 및 실행 관리

use std::process::Command;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// BitVMX 통합 모듈
/// RISC-V toolchain을 사용한 프로그램 컴파일 및 실행 관리
pub struct BitVMXIntegration {
    /// BitVMX 루트 디렉토리
    bitvmx_root: PathBuf,
    /// RISC-V 툴체인 경로
    riscv_toolchain: PathBuf,
    /// Docker compose 사용 여부
    use_docker: bool,
}

impl BitVMXIntegration {
    pub fn new() -> Self {
        let bitvmx_root = PathBuf::from("./bitvmx");
        Self {
            bitvmx_root: bitvmx_root.clone(),
            riscv_toolchain: bitvmx_root.join("riscv-toolchain"),
            use_docker: true, // 기본적으로 Docker 사용
        }
    }

    /// C 프로그램을 RISC-V ELF로 컴파일
    pub async fn compile_program(&self, program_name: &str) -> Result<PathBuf> {
        if self.use_docker {
            // Docker를 통한 컴파일
            let output = Command::new("docker-compose")
                .current_dir(&self.bitvmx_root)
                .args(&[
                    "run", "--rm", "prover-backend",
                    "/app/scripts/compile_program.sh",
                    program_name
                ])
                .output()?;
                
            if !output.status.success() {
                return Err(anyhow::anyhow!("Compilation failed: {}", 
                    String::from_utf8_lossy(&output.stderr)));
            }
        } else {
            // 로컬 RISC-V 툴체인 사용
            let source = self.bitvmx_root.join("execution_files").join(format!("{}.c", program_name));
            let output = self.bitvmx_root.join("execution_files").join(format!("{}.elf", program_name));
            
            let compile_output = Command::new(self.riscv_toolchain.join("bin/riscv32-unknown-elf-gcc"))
                .args(&[
                    "-march=rv32im",
                    "-mabi=ilp32",
                    "-nostdlib",
                    "-T", self.bitvmx_root.join("execution_files/link.ld").to_str().unwrap(),
                    source.to_str().unwrap(),
                    "-o", output.to_str().unwrap()
                ])
                .output()?;
                
            if !compile_output.status.success() {
                return Err(anyhow::anyhow!("RISC-V compilation failed"));
            }
            
            return Ok(output);
        }
        
        Ok(self.bitvmx_root.join("execution_files").join(format!("{}.elf", program_name)))
    }
    
    /// 옵션 정산 프로그램 실행
    pub async fn execute_settlement(
        &self,
        option_type: u32,
        strike_price: u32,
        spot_price: u32,
        quantity: u32,
    ) -> Result<SettlementResult> {
        // 먼저 프로그램 컴파일
        let elf_path = self.compile_program("option_settlement").await?;
        
        // 입력 데이터 준비 (16진수 문자열)
        let input_hex = format!("{:08x}{:08x}{:08x}{:08x}",
            option_type,
            strike_price,
            spot_price,
            quantity
        );
        
        // BitVMX 에뮬레이터 실행
        let emulator_path = self.bitvmx_root.join("BitVMX-CPU/target/release/emulator");
        let output = Command::new(&emulator_path)
            .args(&[
                "execute",
                "--elf", elf_path.to_str().unwrap(),
                "--input", &input_hex,
                "--trace",
            ])
            .output()?;
        
        if !output.status.success() {
            return Err(anyhow::anyhow!("Emulator execution failed"));
        }
        
        // 결과 파싱
        let output_str = String::from_utf8(output.stdout)?;
        let result = self.parse_execution_output(&output_str)?;
        
        Ok(result)
    }
    
    /// Prover 백엔드를 통한 증명 생성
    pub async fn generate_proof(&self, program_name: &str, input_data: &str) -> Result<ProofData> {
        if self.use_docker {
            // Prover API 호출
            let client = reqwest::Client::new();
            let response = client
                .post("http://localhost:8081/prove")
                .json(&serde_json::json!({
                    "program": program_name,
                    "input": input_data
                }))
                .send()
                .await?;
                
            let proof: ProofData = response.json().await?;
            Ok(proof)
        } else {
            // 로컬 증명 생성 (개발용)
            Err(anyhow::anyhow!("Local proof generation not implemented"))
        }
    }
    
    /// Verifier 백엔드를 통한 검증
    pub async fn verify_proof(&self, proof: &ProofData) -> Result<bool> {
        if self.use_docker {
            // Verifier API 호출
            let client = reqwest::Client::new();
            let response = client
                .post("http://localhost:8080/verify")
                .json(proof)
                .send()
                .await?;
                
            #[derive(Deserialize)]
            struct VerifyResponse {
                valid: bool,
            }
            
            let result: VerifyResponse = response.json().await?;
            Ok(result.valid)
        } else {
            Err(anyhow::anyhow!("Local verification not implemented"))
        }
    }
    
    /// 실행 출력 파싱
    fn parse_execution_output(&self, output: &str) -> Result<SettlementResult> {
        // 출력에서 결과 추출 (실제 포맷에 맞게 조정 필요)
        let lines: Vec<&str> = output.lines().collect();
        
        // 마지막 줄에서 결과 추출 (예시)
        if let Some(last_line) = lines.last() {
            if let Ok(payout) = last_line.parse::<u64>() {
                return Ok(SettlementResult {
                    is_itm: payout > 0,
                    payout_amount: payout,
                    trace_hash: [0u8; 32], // 실제로는 트레이스에서 계산
                });
            }
        }
        
        Err(anyhow::anyhow!("Failed to parse execution output"))
    }
}

/// 정산 결과
#[derive(Debug, Serialize, Deserialize)]
pub struct SettlementResult {
    pub is_itm: bool,
    pub payout_amount: u64,
    pub trace_hash: [u8; 32],
}

/// 실행 트레이스
#[derive(Debug, Serialize, Deserialize)]
pub struct ExecutionTrace {
    pub steps: Vec<Step>,
    pub final_state: State,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Step {
    pub pc: u32,
    pub instruction: u32,
    pub registers: [u32; 32],
}

#[derive(Debug, Serialize, Deserialize)]
pub struct State {
    pub registers: [u32; 32],
    pub memory: Vec<u8>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ProofData {
    pub program_hash: String,
    pub input_hash: String,
    pub output_hash: String,
    pub trace_hash: String,
    pub merkle_proof: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_integration_setup() {
        let integration = BitVMXIntegration::new();
        assert!(integration.bitvmx_root.exists());
    }
    
    // Docker가 필요한 테스트는 ignore
    #[tokio::test]
    #[ignore]
    async fn test_compile_program() {
        let integration = BitVMXIntegration::new();
        let result = integration.compile_program("hello_world").await;
        assert!(result.is_ok());
    }
}