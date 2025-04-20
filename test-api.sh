#!/bin/bash

echo "Testing minimal user registration..."
curl -X POST -H "Content-Type: application/json" -d @test-register-minimal.json http://localhost:3000/api/add-user

echo -e "\n\nTesting full user registration..."
curl -X POST -H "Content-Type: application/json" -d @test-register.json http://localhost:3000/api/add-user 