import unittest
from ai import validate_topic, generate_references

class TestBlogWriter(unittest.TestCase):
    def test_topic_validator_structure(self):
        # Verify validator output structure
        res = validate_topic("Climate Change")
        self.assertIn("valid", res)
        self.assertIn("reason", res)

    def test_generate_references_deduplication(self):
        # Verify references deduplicate links correctly
        main_res = {
            "findings": [
                {"url": "https://example.com/1", "title": "Source 1"},
                {"url": "https://example.com/2", "title": "Source 2"}
            ]
        }
        sec_res = [
            {"facts": [{"source": "https://example.com/1"}, {"source": "https://example.com/3"}]}
        ]
        res = generate_references(main_res, sec_res)
        urls = [r["url"] for r in res["references"]]
        
        self.assertEqual(len(urls), 3) # Should deduplicate url 1
        self.assertEqual(res["references"][0]["id"], 1)

if __name__ == "__main__":
    unittest.main()
