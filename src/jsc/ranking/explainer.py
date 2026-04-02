"""Match explanation generator — template-based, no LLM needed."""

from jsc.schemas.match import ComponentExplanation, MatchExplanation


def _grade(score: float) -> str:
    """Map 0-1 score to letter grade."""
    if score >= 0.90:
        return "A+"
    elif score >= 0.80:
        return "A"
    elif score >= 0.70:
        return "B+"
    elif score >= 0.60:
        return "B"
    elif score >= 0.50:
        return "C"
    elif score >= 0.35:
        return "D"
    return "F"


class MatchExplainer:
    """Generates human-readable explanations from scorer results."""

    def explain(
        self,
        overall_score: float,
        components: list[tuple[str, float, float, dict]],
    ) -> MatchExplanation:
        """Build explanation from scoring components.

        Args:
            overall_score: Final weighted score.
            components: List of (name, weight, score, details) tuples.
        """
        grade = _grade(overall_score)
        strengths: list[str] = []
        gaps: list[str] = []
        component_explanations: list[ComponentExplanation] = []

        for name, weight, score, details in components:
            weighted = weight * score
            component_explanations.append(
                ComponentExplanation(
                    name=name,
                    weight=weight,
                    score=round(score, 3),
                    weighted_score=round(weighted, 3),
                    details=details,
                )
            )

            # Generate strengths and gaps
            if name == "Semantic Similarity":
                if score >= 0.80:
                    strengths.append("Strong overall profile alignment")
                elif score < 0.50:
                    gaps.append("Low overall profile alignment — job may be in a different domain")

            elif name == "Skill Coverage":
                missing = details.get("missing_required", [])
                matched = details.get("matched_required", [])
                if score >= 0.80:
                    strengths.append(
                        f"Excellent skill coverage — {len(matched)} required skills matched"
                    )
                elif missing:
                    gaps.append(
                        f"Missing {len(missing)} required skill(s): {', '.join(missing[:5])}"
                    )

            elif name == "Title/Role Match":
                if details.get("role_family_match"):
                    strengths.append(
                        f"Role family match — your experience as "
                        f"'{details.get('best_candidate_title', '')}' aligns well"
                    )
                elif score < 0.3:
                    gaps.append("Job title doesn't closely match your role history")

            elif name == "Seniority Match":
                diff = details.get("level_difference", 0)
                if diff == 0:
                    strengths.append("Seniority level is a perfect match")
                elif diff >= 2:
                    c_sen = details.get("candidate_seniority", "unknown")
                    j_sen = details.get("job_seniority", "unknown")
                    gaps.append(
                        f"Seniority mismatch — you're {c_sen}, role is {j_sen}"
                    )

            elif name == "Location/Remote Fit":
                match_type = details.get("match_type", "")
                if "match" in match_type and score >= 0.8:
                    strengths.append("Location/remote arrangement works for you")
                elif score == 0.0:
                    gaps.append(
                        f"Location mismatch — job is onsite at {details.get('job_location', 'unknown')}"
                    )

        # Build summary
        if overall_score >= 0.80:
            summary = "Strong match"
        elif overall_score >= 0.60:
            summary = "Good match with some gaps"
        elif overall_score >= 0.40:
            summary = "Partial match — several areas of misalignment"
        else:
            summary = "Weak match"

        if strengths:
            summary += f". {strengths[0]}."
        if gaps:
            summary += f" {gaps[0]}."

        return MatchExplanation(
            overall_score=round(overall_score, 3),
            grade=grade,
            summary=summary,
            components=component_explanations,
            strengths=strengths,
            gaps=gaps,
        )
