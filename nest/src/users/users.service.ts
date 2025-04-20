import { Injectable, NotFoundException, UnauthorizedException } from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';
import { RoleEnum } from './users.controller';
import * as bcrypt from 'bcryptjs'; // تغییر به bcryptjs

@Injectable()
export class UserService {
  constructor(private prisma: PrismaService) {}

  // ایجاد کاربر جدید
  async create(createUserDto: CreateUserDto) {
    try {
      // هش کردن رمز عبور
      const hashedPassword = await bcrypt.hash(createUserDto.password, 10);
    
      // پیدا کردن کلاس بر اساس رشته و پایه
      const classRecord = await this.prisma.class.findFirst({
        where: {
          majorId: createUserDto.majorId,
          gradeId: createUserDto.gradeId,
        },
      });
      
      // تبدیل مقادیر به اعداد صحیح
      const majorId = typeof createUserDto.majorId === 'string' 
        ? parseInt(createUserDto.majorId, 10) 
        : createUserDto.majorId;
      
      const gradeId = typeof createUserDto.gradeId === 'string' 
        ? parseInt(createUserDto.gradeId, 10) 
        : createUserDto.gradeId;
      
      const roleId = typeof createUserDto.roleId === 'string' 
        ? parseInt(createUserDto.roleId, 10) 
        : createUserDto.roleId;
      
      const classId = classRecord ? classRecord.id : null;
      
      // استفاده از کوئری خام SQL برای اطمینان از اینکه مشکل auto_increment حل شود
      const query = `
        INSERT INTO \`user\` 
        (\`fullName\`, \`nationalCode\`, \`phoneNumber\`, \`password\`, \`roleId\`, \`majorId\`, \`gradeId\`, \`classId\`) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `;
      
      const values = [
        createUserDto.fullName,
        createUserDto.nationalCode,
        createUserDto.phoneNumber,
        hashedPassword,
        roleId,
        majorId,
        gradeId,
        classId
      ];
      
      console.log('Executing raw SQL query with values:', values);
      
      await this.prisma.$executeRawUnsafe(query, ...values);
      
      // بعد از درج، کاربر را با کد ملی بازیابی می‌کنیم
      return this.findByNationalCode(createUserDto.nationalCode);
    } catch (error) {
      console.error('Error creating user:', error);
      throw error;
    }
  }
  


  // دریافت لیست تمامی کاربران
  async findAll() {
    return this.prisma.user.findMany({
      include: { role: true },
    });
  }

  // پیدا کردن یک کاربر بر اساس ID
  async findOne(id: number) {
    const user = await this.prisma.user.findUnique({
      where: { id },
      include: { role: true },
    });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  // پیدا کردن کاربر بر اساس کد ملی
  async findByNationalCode(nationalCode: string) {
    const user = await this.prisma.user.findUnique({
      where: { nationalCode },
      include: { role: true },
    });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  // ویرایش اطلاعات کاربر
  async update(id: number, updateUserDto: UpdateUserDto) {
    const userExists = await this.prisma.user.findUnique({
      where: { id },
    });
    if (!userExists) throw new NotFoundException('User not found');

    // اگر رمز عبور جدید داده شده، آن را هش کنید
    const hashedPassword = updateUserDto.password ? await bcrypt.hash(updateUserDto.password, 10) : userExists.password;

    return await this.prisma.user.update({
      where: { id },
      data: {
        fullName: updateUserDto.fullName,
        nationalCode: updateUserDto.nationalCode,
        phoneNumber: updateUserDto.phoneNumber,
        password: hashedPassword, // ذخیره کردن رمز عبور هش‌شده
        roleId: updateUserDto.roleId,
      },
    });
  }

  // حذف کاربر بر اساس ID
  async remove(id: number) {
    const userExists = await this.prisma.user.findUnique({
      where: { id },
    });
    if (!userExists) throw new NotFoundException('User not found');

    return await this.prisma.user.delete({
      where: { id },
    });
  }

  // به‌روزرسانی نقش کاربر
  async updateRole(id: number, roleId: number) {
    const userExists = await this.prisma.user.findUnique({
      where: { id },
    });
    if (!userExists) throw new NotFoundException('User not found');

    return await this.prisma.user.update({
      where: { id },
      data: { roleId },
    });
  }

  // دریافت ID نقش بر اساس نام
  async getRoleIdByName(roleName: RoleEnum): Promise<number> {
    const role = await this.prisma.role.findUnique({
      where: { name: roleName },
    });
    if (!role) throw new NotFoundException('Role not found'); // اضافه کردن خطا در صورت عدم وجود نقش
    return role.id;
  }
}
