package com.demo.employee.controller;
import com.demo.employee.entity.Employee;
import com.demo.employee.service.EmployeeService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/employees")
public class EmployeeController {
 private final EmployeeService service;
 public EmployeeController(EmployeeService service) { this.service=service; }
 @PostMapping
 public ResponseEntity<Employee> create(@RequestBody Employee employee) {
  return ResponseEntity.status(HttpStatus.CREATED).body(service.create(employee));
 }
 @GetMapping("/{id}")
 public ResponseEntity<Employee> findById(@PathVariable Long id) {
  return service.findById(id).map(ResponseEntity::ok)
   .orElseGet(() -> ResponseEntity.notFound().build());
 }
}
