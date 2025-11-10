set -e
curl -s http://localhost/users/users && echo
curl -s http://localhost/catalog/products && echo
curl -s http://localhost/orders/orders && echo
curl -s -X POST http://localhost/orders/orders -H "Content-Type: application/json" \
  -d '{"user_id":1,"product_id":101,"qty":2}' && echo
curl -s http://localhost/orders/orders && echo
