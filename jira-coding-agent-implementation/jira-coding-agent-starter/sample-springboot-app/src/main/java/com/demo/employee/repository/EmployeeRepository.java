package com.demo.employee.repository;
import com.demo.employee.entity.Employee;
import org.springframework.data.jpa.repository.JpaRepository;
public interface EmployeeRepository extends JpaRepository<Employee, Long> {
 boolean existsByEmail(String email);
}
