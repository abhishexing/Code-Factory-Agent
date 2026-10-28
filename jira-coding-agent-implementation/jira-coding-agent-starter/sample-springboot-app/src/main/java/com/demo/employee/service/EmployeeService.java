package com.demo.employee.service;
import com.demo.employee.entity.Employee;
import com.demo.employee.repository.EmployeeRepository;
import org.springframework.stereotype.Service;
import java.util.Optional;
@Service
public class EmployeeService {
 private final EmployeeRepository repository;
 public EmployeeService(EmployeeRepository repository) { this.repository=repository; }
 public Employee create(Employee employee) { return repository.save(employee); }
 public Optional<Employee> findById(Long id) { return repository.findById(id); }
}
