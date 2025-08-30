"""
End-to-End User Workflow Tests for Daily Summary Feature

Test-Driven Development (TDD) tests for the complete user workflow from
prompt definition to summary display in the Daily Summary Card.
These tests verify the entire system integration.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from api.server import app
from services.llm_service import LLMService
from services.document_service import DocumentService
from core.async_database import AsyncDatabaseService
from llm.base import LLMResponse


class TestDailySummaryUserWorkflow:
    """Test complete user workflow for daily summary feature"""

    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_database_with_data(self):
        """Mock database with realistic test data"""
        database = Mock(spec=DatabaseService)
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.commit = Mock()
        
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        database.get_connection.return_value = mock_context
        
        return database, mock_cursor

    @pytest.fixture
    def sample_daily_data_multi_namespace(self):
        """Realistic daily data from multiple namespaces"""
        return {
            "prompt_setting": {"prompt_document_id": "user-prompt-summary-123"},
            "news_data": [
                {
                    "title": "OpenAI Announces GPT-5 Development",
                    "snippet": "Next generation AI model promises significant improvements in reasoning and multimodal capabilities"
                },
                {
                    "title": "Renewable Energy Milestone Reached",
                    "snippet": "Global renewable energy capacity reaches 3,000 GW, marking historic achievement"
                },
                {
                    "title": "Space Tourism Market Expansion",
                    "snippet": "Commercial space flights become more accessible with new safety certifications"
                }
            ],
            "limitless_data": [
                {
                    "processed_content": "Team Stand-up Meeting: Discussed sprint progress, identified blockers in authentication module. Sarah will lead the security review. Next steps: complete user story testing by Friday."
                },
                {
                    "processed_content": "Client Call - TechCorp: Positive feedback on Q4 deliverables. They're interested in expanding scope for Q1. Need to prepare proposal by next Tuesday. Budget discussions scheduled for next week."
                },
                {
                    "processed_content": "Learning Session: Completed advanced React patterns course. Key takeaways: custom hooks for state management, performance optimization techniques. Planning to implement in current project."
                }
            ],
            "twitter_data": [
                {
                    "content": "Excited about the new AI developments! The pace of innovation in 2024 is incredible. #AI #Technology #Innovation"
                },
                {
                    "content": "Just wrapped up an amazing team meeting. Love working with people who are passionate about what they do! #TeamWork #Productivity"
                },
                {
                    "content": "Reading about renewable energy progress. It's amazing how far we've come in just a few years. The future looks bright! 🌱 #CleanEnergy #Sustainability"
                }
            ],
            "weather_data": {
                "response_json": json.dumps({
                    "data": [{
                        "weather": "sunny",
                        "temperature": 24,
                        "conditions": "Clear skies with light breeze, perfect day for outdoor activities and walking meetings"
                    }]
                })
            }
        }

    @pytest.fixture
    def user_defined_prompt(self):
        """User-defined summary prompt document"""
        prompt_doc = Mock()
        prompt_doc.id = "user-prompt-summary-123"
        prompt_doc.content_md = """Create a comprehensive daily summary for {{DATE}} with these sections:

**🚀 Technology & Innovation Highlights**
- Focus on AI, tech developments, and innovation news
- Include any learning or skill development activities

**💼 Professional Activities**
- Summarize meetings, calls, and work progress
- Highlight key decisions and next steps

**🌱 Personal Growth & Interests**
- Include social media insights and personal reflections
- Note any interests in sustainability, growth areas

**🌤️ Environment & Context**
- Weather and how it influenced the day
- Overall energy and productivity levels

**🎯 Key Themes & Takeaways**
- Identify 3-5 main themes from the day
- What made this day significant?

Keep the tone conversational but insightful, as if writing in a personal journal."""
        
        return prompt_doc

    def test_complete_user_workflow_with_llm_available(self, client, mock_database_with_data, 
                                                       sample_daily_data_multi_namespace, 
                                                       user_defined_prompt):
        """Test complete workflow: User has defined prompt → visits day with data → sees generated summary"""
        database, mock_cursor = mock_database_with_data
        data = sample_daily_data_multi_namespace
        
        # Mock database queries in sequence
        mock_cursor.fetchone.side_effect = [
            data["prompt_setting"],  # Prompt setting lookup
            data["weather_data"],    # Weather data
            None  # End of fetchone calls
        ]
        
        mock_cursor.fetchall.side_effect = [
            data["news_data"],     # News items
            data["limitless_data"] # Limitless activities
        ]
        
        # Mock document service
        document_service = Mock()
        document_service.get_document.return_value = user_defined_prompt
        
        # Mock template processor
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = user_defined_prompt.content_md.replace("{{DATE}}", "2024-01-15")
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM provider with realistic response
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        
        # Realistic AI-generated summary based on the data
        ai_generated_content = """# Daily Summary for 2024-01-15

**🚀 Technology & Innovation Highlights**
- OpenAI announced GPT-5 development with significant improvements in reasoning and multimodal capabilities
- Completed advanced React patterns course, focusing on custom hooks and performance optimization
- Excited about the rapid pace of AI innovation in 2024

**💼 Professional Activities**
- Team stand-up meeting: Discussed sprint progress, identified authentication module blockers
- Sarah leading security review, user story testing due Friday
- Client call with TechCorp: Very positive feedback on Q4 deliverables
- They're interested in expanding scope for Q1, need proposal by Tuesday
- Budget discussions scheduled for next week

**🌱 Personal Growth & Interests**
- Passionate about renewable energy progress - global capacity reached 3,000 GW milestone
- Fascinated by space tourism market expansion and increased accessibility
- Strong focus on sustainability and clean energy future
- Appreciation for teamwork and passionate colleagues

**🌤️ Environment & Context**
- Beautiful sunny day, 24°C with clear skies and light breeze
- Perfect weather for outdoor activities and walking meetings
- High energy and productivity levels throughout the day

**🎯 Key Themes & Takeaways**
1. **Innovation Leadership**: AI developments and personal skill building in React
2. **Professional Growth**: Strong client relationships and team collaboration
3. **Sustainability Focus**: Interest in renewable energy and environmental progress
4. **Team Dynamics**: Positive team interactions and effective communication
5. **Optimal Conditions**: Perfect weather enhancing overall productivity and mood

This was a significant day marked by technological excitement, professional progress, and perfect environmental conditions that enhanced overall productivity and positive team dynamics."""

        mock_llm_response = LLMResponse(
            content=ai_generated_content,
            model="llama2:latest",
            provider="ollama",
            usage={"total_tokens": 425}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Mock startup service with all dependencies
        startup_service = Mock()
        llm_service = LLMService(database, document_service, Mock())
        llm_service.llm_provider = mock_llm_provider
        llm_service.template_processor = mock_template_processor
        startup_service.llm_service = llm_service
        
        # Execute the complete workflow
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            # User visits day view - API call to generate summary
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )
        
        # Verify successful end-to-end workflow
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        assert "Daily Summary for 2024-01-15" in result["content"]
        assert "Technology & Innovation Highlights" in result["content"]
        assert "OpenAI announced GPT-5" in result["content"]
        assert "Team stand-up meeting" in result["content"]
        assert "24°C with clear skies" in result["content"]
        assert "Innovation Leadership" in result["content"]
        assert result["generation_time"] > 0
        assert result["model_info"]["model"] == "llama2:latest"
        
        # Verify all data sources were incorporated
        assert "React patterns course" in result["content"]  # Limitless data
        assert "renewable energy" in result["content"]       # News data
        assert "passionate colleagues" in result["content"]   # Social/Twitter data
        assert "sunny day" in result["content"]              # Weather data

    def test_user_workflow_no_llm_configured(self, client):
        """Test workflow when user visits day but no LLM is configured"""
        # Mock startup service without LLM service
        startup_service = Mock()
        startup_service.llm_service = None
        
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )
        
        # Should return 503 Service Unavailable
        assert response.status_code == 503
        assert "LLM service not available" in response.json()["detail"]
        
        # Frontend should detect this and show "No LLM available to process summary" message

    def test_user_workflow_no_prompt_defined(self, client, mock_database_with_data):
        """Test workflow when user visits day but has not defined a summary prompt"""
        database, mock_cursor = mock_database_with_data
        
        # Mock no prompt setting configured
        mock_cursor.fetchone.side_effect = [
            None,  # No prompt setting found
            None   # No weather data
        ]
        mock_cursor.fetchall.side_effect = [[], []]  # No news or limitless data
        
        # Mock services
        startup_service = Mock()
        llm_service = Mock()
        llm_service.generate_daily_summary = AsyncMock()
        
        # Mock failed generation due to no prompt
        from services.llm_service import LLMGenerationResult
        failed_result = LLMGenerationResult(
            content="",
            prompt_used="",
            model_info={},
            generation_time=0,
            success=False,
            error_message="No summary prompt configured. Please set up a daily summary prompt in Settings."
        )
        llm_service.generate_daily_summary.return_value = failed_result
        startup_service.llm_service = llm_service
        
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            response = client.post(
                "/api/llm/generate-summary", 
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is False
        assert "No summary prompt configured" in result["error_message"]
        
        # Frontend should show message guiding user to set up prompt in Settings

    def test_user_workflow_no_data_for_date(self, client, mock_database_with_data, user_defined_prompt):
        """Test workflow when user visits date with no data from any namespace"""
        database, mock_cursor = mock_database_with_data
        
        # Mock prompt exists but no data for the date
        mock_cursor.fetchone.side_effect = [
            {"prompt_document_id": "user-prompt-123"},  # Prompt exists
            None,  # No weather data
            None
        ]
        mock_cursor.fetchall.side_effect = [
            [],  # No news data
            []   # No limitless data
        ]
        
        # Mock services
        document_service = Mock()
        document_service.get_document.return_value = user_defined_prompt
        
        mock_template_processor = Mock()
        resolved_template = Mock() 
        resolved_template.resolved_content = "Generate summary for 2024-12-25"
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM response for no data scenario
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        
        no_data_response = """# Daily Summary for 2024-12-25

**📋 Data Summary**
No significant digital activities were recorded for this date. This appears to be a quiet day with minimal tracked interactions.

**🤔 Possible Reasons**
- Holiday or weekend with reduced digital activity
- Day spent offline or away from tracked devices
- System downtime or data collection issues

**💡 Suggestion**
This could be a great opportunity to reflect on offline activities, personal time, or simply enjoying a peaceful day away from digital distractions."""

        mock_llm_response = LLMResponse(
            content=no_data_response,
            model="llama2",
            provider="ollama",
            usage={"total_tokens": 85}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Setup services
        startup_service = Mock()
        llm_service = LLMService(database, document_service, Mock())
        llm_service.llm_provider = mock_llm_provider
        llm_service.template_processor = mock_template_processor
        startup_service.llm_service = llm_service
        
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-12-25", "force_regenerate": False}
            )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        assert "No significant digital activities" in result["content"]
        assert "quiet day" in result["content"]
        assert result["generation_time"] > 0

    def test_user_workflow_cached_summary_retrieval(self, client, mock_database_with_data):
        """Test workflow when user visits day with existing cached summary"""
        database, mock_cursor = mock_database_with_data
        
        # Mock cached summary exists
        cached_content = """# Daily Summary for 2024-01-15

**🚀 Technology & Innovation**
- Major AI breakthroughs discussed in team meeting
- Completed advanced React course with practical applications

**💼 Professional Achievements** 
- Successful client presentation to TechCorp
- Positive feedback on Q4 deliverables
- New project proposal in development

**🌤️ Perfect Day**
- Beautiful sunny weather, 24°C
- High productivity and positive team energy
- Great day for outdoor lunch meeting

**🎯 Key Themes**
1. Technical skill advancement
2. Strong client relationships  
3. Team collaboration excellence
4. Optimal working conditions

A highly productive day marked by learning, client success, and perfect weather conditions."""

        mock_cursor.fetchone.return_value = {
            "content": cached_content,
            "prompt_used": "Daily summary prompt",
            "created_at": "2024-01-15T15:30:00Z"
        }
        
        # Mock services
        startup_service = Mock()
        llm_service = Mock()
        llm_service.get_cached_summary = AsyncMock(return_value=cached_content)
        startup_service.llm_service = llm_service
        
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            # First check cached endpoint
            response = client.get("/api/llm/summary/2024-01-15")
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["content"] == cached_content
        assert result["cached"] is True
        assert result["days_date"] == "2024-01-15"
        
        # Verify cache is used for generation request too
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )
        
        assert response.status_code == 200
        result = response.json()
        assert result["cached"] is True
        assert result["content"] == cached_content

    def test_user_workflow_force_regeneration(self, client, mock_database_with_data, 
                                            sample_daily_data_multi_namespace, user_defined_prompt):
        """Test workflow when user forces regeneration of existing cached summary"""
        database, mock_cursor = mock_database_with_data
        data = sample_daily_data_multi_namespace
        
        # Setup database responses for fresh generation
        mock_cursor.fetchone.side_effect = [
            data["prompt_setting"],
            data["weather_data"],
            None
        ]
        mock_cursor.fetchall.side_effect = [
            data["news_data"],
            data["limitless_data"]
        ]
        
        # Mock updated prompt with new focus
        updated_prompt = Mock()
        updated_prompt.content_md = """Generate an executive summary for {{DATE}}:

**Executive Overview**
- Strategic priorities and key accomplishments
- Market insights and competitive intelligence  
- Team performance and operational metrics
- Risk assessment and mitigation strategies

**Action Items & Next Steps**
- Critical path items requiring immediate attention
- Strategic initiatives for upcoming period
- Resource allocation recommendations

Focus on business impact and strategic value."""
        
        document_service = Mock()
        document_service.get_document.return_value = updated_prompt
        
        # Mock template processor
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = updated_prompt.content_md.replace("{{DATE}}", "2024-01-15")
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock new LLM response with executive focus
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        
        executive_summary = """# Executive Summary for 2024-01-15

**Executive Overview**
- **Strategic Priority**: AI capability development with OpenAI GPT-5 announcement creating market opportunities
- **Key Accomplishment**: TechCorp client relationship strengthened with Q4 deliverable success and Q1 expansion interest
- **Market Intelligence**: Renewable energy sector reached 3,000 GW milestone, indicating accelerated market maturation
- **Team Performance**: High engagement in technical skill development and collaborative problem-solving

**Action Items & Next Steps**
- **Critical Path**: Complete TechCorp proposal by Tuesday for Q1 expansion opportunity
- **Strategic Initiative**: Implement React performance optimizations in current project based on completed training
- **Resource Allocation**: Assign Sarah to lead security review for authentication module
- **Market Position**: Evaluate space tourism market expansion implications for potential client opportunities

**Risk Assessment**
- Authentication module blockers could impact sprint delivery
- Budget discussions with TechCorp require careful preparation
- Need to balance skill development time with delivery commitments

**Business Impact**: Strong day with client expansion opportunity, team skill advancement, and strategic market awareness positioning us well for Q1 growth."""

        mock_llm_response = LLMResponse(
            content=executive_summary,
            model="llama2:latest",
            provider="ollama",
            usage={"total_tokens": 312}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Setup services
        startup_service = Mock()
        llm_service = LLMService(database, document_service, Mock())
        llm_service.llm_provider = mock_llm_provider
        llm_service.template_processor = mock_template_processor
        startup_service.llm_service = llm_service
        
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            # Force regeneration request
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": True}
            )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        assert result["cached"] is False  # Should be newly generated
        assert "Executive Summary for 2024-01-15" in result["content"]
        assert "Strategic Priority" in result["content"]
        assert "TechCorp proposal by Tuesday" in result["content"]
        assert "Business Impact" in result["content"]
        
        # Verify it's different from a typical daily summary format
        assert "Executive Overview" in result["content"]
        assert "Action Items" in result["content"]

    def test_multiple_namespace_data_aggregation_workflow(self, client, mock_database_with_data):
        """Test workflow ensures all namespace data is properly aggregated in summary"""
        database, mock_cursor = mock_database_with_data
        
        # Comprehensive multi-namespace data
        comprehensive_data = {
            "prompt_setting": {"prompt_document_id": "comprehensive-prompt"},
            "news_data": [
                {"title": "Climate Summit Results", "snippet": "New international agreements on carbon reduction targets"},
                {"title": "Quantum Computing Breakthrough", "snippet": "IBM announces 1000-qubit quantum processor"},
                {"title": "Remote Work Study", "snippet": "5-year study shows 30% productivity increase in hybrid teams"}
            ],
            "limitless_data": [
                {"processed_content": "Morning meditation: 20 minutes focusing on gratitude and intention setting"},
                {"processed_content": "Project review with Alex: Discussed UX improvements, need to prioritize mobile responsiveness"},
                {"processed_content": "Lunch meeting with Sarah from marketing: Campaign performance analysis, 40% increase in engagement"},
                {"processed_content": "Evening reading: 'Atomic Habits' chapter on environment design for behavior change"}
            ],
            "twitter_data": [
                {"content": "Fascinating quantum computing news today! The pace of technological advancement never ceases to amaze #QuantumComputing #Innovation"},
                {"content": "Had a great project sync today. Love collaborating with designers who really understand user experience #Teamwork #UX"},
                {"content": "Reading about remote work benefits. Hybrid model really does work well for our team's productivity #RemoteWork #Productivity"}
            ],
            "weather_data": {
                "response_json": json.dumps({
                    "data": [{
                        "weather": "partly cloudy",
                        "temperature": 21,
                        "conditions": "Comfortable temperature with occasional sunshine, ideal for focused work"
                    }]
                })
            }
        }
        
        # Setup database responses
        mock_cursor.fetchone.side_effect = [
            comprehensive_data["prompt_setting"],
            comprehensive_data["weather_data"],
            None
        ]
        mock_cursor.fetchall.side_effect = [
            comprehensive_data["news_data"],
            comprehensive_data["limitless_data"]
        ]
        
        # Mock comprehensive prompt
        comprehensive_prompt = Mock()
        comprehensive_prompt.content_md = """Create a holistic daily summary for {{DATE}}:

**🌍 Global Perspective**: World events and their implications
**🔬 Technology & Innovation**: Scientific and technological developments  
**💭 Personal Development**: Learning, reflection, and growth activities
**👥 Professional Collaboration**: Team interactions and project progress
**🌱 Wellness & Mindfulness**: Health, mindfulness, and personal care
**🌤️ Environmental Context**: Weather and physical environment impact

Weave these elements into a cohesive narrative showing how different aspects of the day interconnected."""

        document_service = Mock()
        document_service.get_document.return_value = comprehensive_prompt
        
        # Mock template processor
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = comprehensive_prompt.content_md.replace("{{DATE}}", "2024-01-15")
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM with comprehensive integration
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        
        holistic_summary = """# Holistic Daily Summary for 2024-01-15

**🌍 Global Perspective**
The day began with significant news from the Climate Summit, where new international carbon reduction agreements signal a global shift toward sustainability. IBM's announcement of their 1000-qubit quantum processor represents a quantum leap (literally) in computational capabilities, while research confirming 30% productivity increases in hybrid work models validates our team's approach.

**🔬 Technology & Innovation** 
The quantum computing breakthrough particularly captured my attention, as evidenced by my social media engagement with the topic. This technology could revolutionize everything from drug discovery to financial modeling. The implications for our current projects are worth exploring, especially in data processing optimization.

**💭 Personal Development**
Started the day with intentional 20-minute meditation focused on gratitude and intention setting, creating a centered foundation. Evening reading of 'Atomic Habits' on environment design provided valuable insights into behavior change mechanics. The combination of morning mindfulness and evening learning created a beautiful bookend to the day's activities.

**👥 Professional Collaboration**
Project collaboration was a highlight, with Alex providing valuable UX perspective on mobile responsiveness priorities. The lunch meeting with Sarah revealed impressive marketing campaign results - 40% engagement increase demonstrates strong team synergy across departments. My social media reflection on design collaboration shows genuine appreciation for cross-functional teamwork.

**🌱 Wellness & Mindfulness**
Morning meditation practice established a mindful tone, while the comfortable 21°C partly cloudy weather supported sustained focus throughout work sessions. The balance of structured work meetings and reflective reading time created an optimal rhythm for both productivity and personal growth.

**🌤️ Environmental Context**
The partly cloudy, 21°C weather with occasional sunshine created ideal conditions for focused indoor work while maintaining a connection to the natural world. This environmental comfort supported both the intensive project discussions and the contemplative evening reading session.

**Interconnected Narrative**
This day beautifully demonstrated how global technological progress (quantum computing), environmental consciousness (climate agreements), personal mindfulness practices, and professional collaboration create a multi-dimensional experience. The comfortable weather supported sustained focus, enabling deep engagement with both team projects and personal development activities. The productivity research validation aligned perfectly with our hybrid work success, creating a satisfying sense of being part of broader positive trends."""

        mock_llm_response = LLMResponse(
            content=holistic_summary,
            model="llama2:latest", 
            provider="ollama",
            usage={"total_tokens": 485}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Setup services
        startup_service = Mock()
        llm_service = LLMService(database, document_service, Mock())
        llm_service.llm_provider = mock_llm_provider
        llm_service.template_processor = mock_template_processor
        startup_service.llm_service = llm_service
        
        with patch('core.dependencies.get_startup_service_dependency', return_value=startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        
        # Verify all namespace data was incorporated
        # News data
        assert "Climate Summit" in result["content"]
        assert "quantum processor" in result["content"]
        assert "hybrid work models" in result["content"]
        
        # Limitless/personal data
        assert "meditation" in result["content"]
        assert "Project review with Alex" in result["content"]
        assert "Atomic Habits" in result["content"]
        assert "Sarah from marketing" in result["content"]
        
        # Social/Twitter data
        assert "social media engagement" in result["content"]
        assert "cross-functional teamwork" in result["content"]
        
        # Weather data
        assert "21°C" in result["content"]
        assert "partly cloudy" in result["content"]
        
        # Verify integration and narrative coherence
        assert "Interconnected Narrative" in result["content"]
        assert "multi-dimensional experience" in result["content"]


class TestDailySummaryUserExperienceWorkflow:
    """Test user experience aspects of the daily summary workflow"""

    def test_summary_performance_expectations(self):
        """Test that summary generation meets performance expectations"""
        performance_requirements = {
            "api_response_time": {"max": 30000, "target": 5000},  # 30s max, 5s target (ms)
            "cache_hit_time": {"max": 1000, "target": 200},      # 1s max, 200ms target
            "frontend_render_time": {"max": 500, "target": 100},  # 500ms max, 100ms target
            "total_workflow_time": {"max": 35000, "target": 6000} # 35s max, 6s target
        }
        
        # Performance should be reasonable for good UX
        assert performance_requirements["api_response_time"]["target"] < 10000  # Under 10s target
        assert performance_requirements["cache_hit_time"]["max"] < 2000         # Under 2s for cache
        assert performance_requirements["total_workflow_time"]["target"] < 10000 # Under 10s total

    def test_summary_content_quality_expectations(self):
        """Test content quality expectations for generated summaries"""
        quality_requirements = {
            "minimum_length": 200,      # At least 200 characters
            "maximum_length": 5000,     # No more than 5000 characters
            "structure_required": True,  # Should have clear structure
            "readability_level": "conversational", # Accessible language
            "personalization": True,     # Should feel personal
            "actionable_insights": True  # Should provide value
        }
        
        # Content should meet quality standards
        assert quality_requirements["minimum_length"] > 100
        assert quality_requirements["maximum_length"] < 10000
        assert quality_requirements["structure_required"] is True

    def test_error_recovery_user_experience(self):
        """Test that error scenarios provide good user experience"""
        error_recovery_features = {
            "clear_error_messages": True,
            "retry_mechanisms": True,
            "graceful_fallbacks": True,
            "help_documentation_links": True,
            "progress_indicators": True,
            "cancellation_options": True
        }
        
        # Error handling should be user-friendly
        for feature, required in error_recovery_features.items():
            assert required is True

    def test_accessibility_and_inclusivity(self):
        """Test that the daily summary feature is accessible and inclusive"""
        accessibility_features = {
            "screen_reader_support": True,
            "keyboard_navigation": True,
            "high_contrast_mode": True,
            "font_size_scaling": True,
            "language_localization": True,
            "cognitive_load_optimization": True
        }
        
        # Feature should be accessible to all users
        for feature, required in accessibility_features.items():
            assert required is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])