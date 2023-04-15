import unittest
from fastapi.testclient import TestClient

from nft_server_testnet import app, collections

client = TestClient(app)


class TestNFTServer(unittest.TestCase):
    def test_get_offers_valid_collection(self):
        collection_slug = collections[0]
        response = client.get(f"/offers/{collection_slug}")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        for offer in response.json():
            self.assertIsInstance(offer["id"], int)
            self.assertIsInstance(offer["price"], float)
            self.assertIsInstance(offer["link"], str)

    def test_get_offers_invalid_collection(self):
        collection_slug = "non_existent_collection"
        response = client.get(f"/offers/{collection_slug}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"error": "Collection not found"}])  # Update this line

if __name__ == "__main__":
    unittest.main()
