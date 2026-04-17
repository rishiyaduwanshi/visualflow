"""
Mermaid.js Diagram Service - AI-powered diagram generation with validation and auto-retry
"""

import logging
import json
from typing import Dict, Optional, Tuple, List
from config.env_config import EnvConfig
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage

# Import specialized prompts
from .prompts.analyzer_prompt import ANALYZER_PROMPT
from .prompts.flowchart_prompt import FLOWCHART_PROMPT
from .prompts.class_diagram_prompt import CLASS_DIAGRAM_PROMPT
from .prompts.er_diagram_prompt import ER_DIAGRAM_PROMPT
from .prompts.sequence_diagram_prompt import SEQUENCE_DIAGRAM_PROMPT
from .prompts.state_diagram_prompt import STATE_DIAGRAM_PROMPT
from .prompts.dfd_prompt import DFD_PROMPT
from .prompts.system_design_prompt import SYSTEM_DESIGN_PROMPT
from .prompts.custom_prompt import CUSTOM_PROMPT

# Import validator
from .validator import validator

logger = logging.getLogger(__name__)


class MermaidService:
    """
    Service for generating Mermaid.js diagrams using two-step AI approach:
    Step 1: Analyze user prompt and enhance it
    Step 2: Generate diagram with specialized prompt for that diagram type
    """
    
    def __init__(self):
        """Initialize Mermaid service"""
        # Map diagram types to their specialized prompts
        self.prompt_map = {
            'flowchart': FLOWCHART_PROMPT,
            'sequence': SEQUENCE_DIAGRAM_PROMPT,
            'class': CLASS_DIAGRAM_PROMPT,
            'uml': CLASS_DIAGRAM_PROMPT,
            'er': ER_DIAGRAM_PROMPT,
            'erd': ER_DIAGRAM_PROMPT,
            'state': STATE_DIAGRAM_PROMPT,
            'dfd': DFD_PROMPT,
            'system_design': SYSTEM_DESIGN_PROMPT,
            'custom': CUSTOM_PROMPT,
        }
        
        # Initialize AI client
        try:
            self.groq_client = ChatGroq(
                groq_api_key=EnvConfig.GROQ_API_KEY,
                model_name="openai/gpt-oss-120b",
                temperature=0.3
            )
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            self.groq_client = None
    
    def generate_mermaid_code(self, prompt: str, diagram_type: str = 'flowchart') -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Generate Mermaid.js code using AI based on prompt and diagram type
        
        Args:
            prompt (str): User prompt describing the diagram
            diagram_type (str): Type of diagram to generate
            
        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: (mermaid_code, error_message, detected_diagram_type)
        """
        try:
            if not prompt.strip():
                return None, "Prompt cannot be empty", None
            
            # Use AI to generate if available
            if self.groq_client:
                return self._generate_with_ai(prompt, diagram_type)
            else:
                # Fallback to templates
                code, error = self._generate_fallback(prompt, diagram_type)
                return code, error, None
            
        except Exception as e:
            error_msg = f"Error generating Mermaid code: {str(e)}"
            logger.error(error_msg)
            return None, error_msg, None
            
    def _generate_with_ai(self, prompt: str, diagram_type: str, max_retries: int = 3) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Generate Mermaid code using AI with validation and limited auto-retry
        
        Flow:
        1. Analyze and enhance user prompt
        2. Generate diagram with specialized prompt
        3. Validate and fix syntax
        4. If validation fails, retry ONCE with error feedback to AI
        
        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: (mermaid_code, error_message, detected_diagram_type)
        """
        try:
            # STEP 1: Analyze user prompt to understand intent
            logger.info(f"📊 Analyzing prompt for diagram type: {diagram_type}")
            analysis = self._analyze_prompt(prompt, diagram_type)
            
            detected_type = None
            if not analysis:
                logger.warning("⚠️ Analysis failed, using original prompt")
                enhanced_prompt = prompt
                final_diagram_type = diagram_type
            else:
                enhanced_prompt = analysis.get('enhanced_prompt', prompt)
                detected_type = analysis.get('diagram_type', diagram_type)
                
                # Use analyzed diagram type if confidence is high
                if analysis.get('confidence', 0) > 0.7:
                    final_diagram_type = detected_type
                else:
                    final_diagram_type = diagram_type
                
                logger.info(f"✅ Analysis complete: {final_diagram_type}")
            
            # STEP 2: Generate with limited retries and validation
            mermaid_code = None
            last_error = None
            last_validation_errors = []
            previous_code = None
            
            for attempt in range(max_retries):
                logger.info(f"🔄 Generation attempt {attempt + 1}/{max_retries}")
                
                # Generate diagram
                if attempt == 0:
                    # First attempt: use enhanced prompt
                    mermaid_code = self._generate_with_specialized_prompt(enhanced_prompt, final_diagram_type)
                else:
                    # Retry with error feedback (only once)
                    retry_prompt = self._create_retry_prompt(
                        original_prompt=enhanced_prompt,
                        fixed_candidate=mermaid_code or "",
                        validation_error=last_error,
                        validation_errors=last_validation_errors,
                        attempt=attempt,
                    )
                    mermaid_code = self._generate_with_specialized_prompt(retry_prompt, final_diagram_type)
                
                if not mermaid_code:
                    last_error = "AI failed to generate code"
                    continue
                
                # Check if AI is generating the same code (stuck in loop)
                if previous_code and previous_code.strip() == mermaid_code.strip():
                    logger.warning("⚠️ AI generating same code, breaking retry loop")
                    break
                
                previous_code = mermaid_code
                
                # STEP 3: Validate and fix (with loop protection inside)
                logger.info("🔍 Validating generated code...")
                fixed_code, is_valid, validation_error, validation_errors = validator.validate_with_feedback(mermaid_code)
                
                if is_valid:
                    logger.info(f"✅ Valid code generated on attempt {attempt + 1}")
                    return fixed_code, None, detected_type
                else:
                    logger.warning(f"⚠️ Validation issues: {validation_error}")
                    last_error = validation_error
                    last_validation_errors = validation_errors
                    mermaid_code = fixed_code
            
            # If all retries exhausted, return best effort
            logger.warning(f"⚠️ Used all {max_retries} attempts, returning best effort")
            if mermaid_code:
                return mermaid_code, f"Generated with minor warnings: {last_error}", detected_type
            else:
                # Ultimate fallback - simple valid diagram
                logger.error("❌ No valid code, using fallback template")
                code, error = self._generate_fallback(prompt, diagram_type)
                return code, error, detected_type
            
        except Exception as e:
            logger.error(f"❌ Exception in AI generation: {str(e)}")
            code, error = self._generate_fallback(prompt, diagram_type)
            return code, error, None
    
    def _create_retry_prompt(
        self,
        original_prompt: str,
        fixed_candidate: str,
        validation_error: Optional[str],
        validation_errors: List[str],
        attempt: int,
    ) -> str:
        """
        Create a retry prompt with error feedback for AI
        """
        feedback_lines = "\n".join(f"- {err}" for err in validation_errors[:6])
        summary = validation_error or "Mermaid validation failed"
        return f"""{original_prompt}

IMPORTANT: Previous attempt {attempt} had Mermaid validation issues.
Summary: {summary}

Detailed issues to fix:
{feedback_lines if feedback_lines else '- Unknown syntax issue; ensure strict Mermaid syntax'}

Fix these specific issues:
1. Use ONLY simple alphanumeric node IDs (no special characters, no hyphens)
2. Use complete edge syntax: -->|label| NOT --|label|
3. Don't mix bracket types: use [label] or (label), NOT [(label)]
4. Avoid reserved keywords: end, start, class, style
5. Return ONLY Mermaid code (no markdown fence or explanation)

Previous candidate Mermaid code to correct:
{fixed_candidate}

Generate corrected Mermaid code now."""

    def regenerate_from_render_error(
        self,
        prompt: str,
        diagram_type: str,
        current_code: str,
        render_error: str,
        attempt: int = 1,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Regenerate Mermaid code using real runtime render error feedback.

        Args:
            prompt: Original user prompt
            diagram_type: Diagram type
            current_code: Currently failing Mermaid code
            render_error: Mermaid runtime/parse error from frontend
            attempt: Client-side attempt number

        Returns:
            Tuple[Optional[str], Optional[str]]: (corrected_code, error_message)
        """
        if not self.groq_client:
            return None, "AI service unavailable for runtime repair"

        runtime_issue = f"Mermaid runtime render error: {render_error}"
        retry_prompt = self._create_retry_prompt(
            original_prompt=prompt,
            fixed_candidate=current_code or "",
            validation_error=runtime_issue,
            validation_errors=[runtime_issue],
            attempt=attempt,
        )

        regenerated_code = self._generate_with_specialized_prompt(retry_prompt, diagram_type)
        if not regenerated_code:
            return None, "AI failed to regenerate Mermaid code"

        fixed_code, is_valid, validation_error, validation_errors = validator.validate_with_feedback(regenerated_code)
        if is_valid:
            return fixed_code, None

        second_retry_prompt = self._create_retry_prompt(
            original_prompt=prompt,
            fixed_candidate=fixed_code,
            validation_error=validation_error or runtime_issue,
            validation_errors=validation_errors,
            attempt=attempt + 1,
        )
        second_regenerated = self._generate_with_specialized_prompt(second_retry_prompt, diagram_type)
        if not second_regenerated:
            return fixed_code, validation_error or "Validation failed after runtime repair"

        second_fixed, second_valid, second_error, _ = validator.validate_with_feedback(second_regenerated)
        if second_valid:
            return second_fixed, None

        return second_fixed, second_error or "Runtime repair failed"
    
    def _analyze_prompt(self, prompt: str, diagram_type: str) -> Optional[Dict]:
        """
        STEP 1: Analyze user prompt to understand requirements
        Returns analysis with enhanced prompt
        """
        try:
            user_message = f"""
User Prompt: "{prompt}"
Suggested Diagram Type: {diagram_type}

Analyze this prompt and return the JSON response.
"""
            
            response = self.groq_client.invoke([
                SystemMessage(ANALYZER_PROMPT),
                HumanMessage(user_message)
            ])
            
            # Parse JSON response
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            analysis = json.loads(content)
            logger.info(f"Prompt analysis successful: {analysis.get('diagram_type')} (confidence: {analysis.get('confidence')})")
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse analysis JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Prompt analysis failed: {e}")
            return None
    
    def _generate_with_specialized_prompt(self, prompt: str, diagram_type: str) -> Optional[str]:
        """
        STEP 2: Generate diagram using specialized system prompt for the diagram type
        """
        try:
            # Get the specialized prompt for this diagram type
            system_prompt = self.prompt_map.get(diagram_type)
            
            if not system_prompt:
                logger.warning(f"No specialized prompt for {diagram_type}, using generic approach")
                system_prompt = FLOWCHART_PROMPT  # Default fallback
            
            user_message = f"""
User Request: {prompt}

Generate the {diagram_type} diagram now.
"""
            
            response = self.groq_client.invoke([
                SystemMessage(system_prompt),
                HumanMessage(user_message)
            ])
            
            mermaid_code = response.content.strip()
            logger.info(f"Generated Mermaid code using specialized {diagram_type} prompt")
            
            return mermaid_code
            
        except Exception as e:
            logger.error(f"Specialized prompt generation failed: {e}")
            return None
    
    def _generate_fallback(self, prompt: str, diagram_type: str) -> Tuple[str, str]:
        """
        Generate a simple fallback diagram when AI fails
        """
        logger.warning("Using fallback diagram generation")
        
        if diagram_type == 'flowchart' or diagram_type == 'custom':
            code = """graph TD
    startNode[🎯 Start] --> processNode[⚙️ Process]
    processNode --> decisionNode{❓ Decision}
    decisionNode -->|✅ Yes| successNode[🎉 Success]
    decisionNode -->|❌ No| errorNode[⚠️ Error]
    errorNode --> processNode
    successNode --> endNode[🏁 End]"""
        elif diagram_type == 'sequence':
            code = """sequenceDiagram
    participant User as 👤 User
    participant System as 🖥️ System
    User->>System: 📤 Request
    System-->>User: 📥 Response"""
        elif diagram_type in ['class', 'uml']:
            code = """classDiagram
    class User {
        +String name
        +String email
        +login()
    }"""
        elif diagram_type in ['er', 'erd']:
            code = """erDiagram
    USER {
        string name
        string email
    }"""
        else:
            code = """graph TD
    A[📋 Component A] --> B[📋 Component B]
    B --> C[📋 Component C]"""
        
        return code, "Using fallback diagram template"
            
    def test_service(self) -> Tuple[bool, Optional[str]]:
        """
        Test the Mermaid service
        
        Returns:
            Tuple[bool, Optional[str]]: (is_working, error_message)
        """
        try:
            test_code, error, _ = self.generate_mermaid_code("test diagram", "flowchart")
            if test_code:
                return True, None
            else:
                return False, error
        except Exception as e:
            return False, str(e)


mermaid_service = MermaidService()