import { Injectable, NotFoundException, UnauthorizedException } from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';
import { RoleEnum } from './users.controller';
import * as bcrypt from 'bcryptjs'; // ØªØºÛŒÛŒØ± Ø¨Ù‡ bcryptjs

@Injectable()
export class UserService {
  constructor(private prisma: PrismaService) {}

  // Ø§ÛŒØ¬Ø§Ø¯ Ú©Ø§Ø±Ø¨Ø± Ø¬Ø¯ÛŒØ¯
  async create(createUserDto: CreateUserDto) {
    try {
      // Ù‡Ø´ Ú©Ø±Ø¯Ù† Ø±Ù…Ø² Ø¹Ø¨ÙˆØ±
      const hashedPassword = await bcrypt.hash(createUserDto.password, 10);
    
      // Ù¾ÛŒØ¯Ø§ Ú©Ø±Ø¯Ù† Ú©Ù„Ø§Ø³ Ø¨Ø± Ø§Ø³Ø§Ø³ Ø±Ø´ØªÙ‡ Ùˆ Ù¾Ø§ÛŒÙ‡
      const classRecord = await this.prisma.class.findFirst({
        where: {
          majorId: createUserDto.majorId,
          gradeId: createUserDto.gradeId,
        },
      });
      
      // ØªØ¨Ø¯ÛŒÙ„ Ù…Ù‚Ø§Ø¯ÛŒØ± Ø¨Ù‡ Ø§Ø¹Ø¯Ø§Ø¯ ØµØ­ÛŒØ­
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
      
      // Ø§Ø³ØªÙØ§Ø¯Ù‡ Ø§Ø² Ú©ÙˆØ¦Ø±ÛŒ Ø®Ø§Ù… SQL Ø¨Ø±Ø§ÛŒ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø§Ø² Ø§ÛŒÙ†Ú©Ù‡ Ù…Ø´Ú©Ù„ auto_increment Ø­Ù„ Ø´ÙˆØ¯
      const query = `
        INSERT INTO \`User\` 
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
      
      // Ø¨Ø¹Ø¯ Ø§Ø² Ø¯Ø±Ø¬ØŒ Ú©Ø§Ø±Ø¨Ø± Ø±Ø§ Ø¨Ø§ Ú©Ø¯ Ù…Ù„ÛŒ Ø¨Ø§Ø²ÛŒØ§Ø¨ÛŒ Ù…ÛŒâ€ŒÚ©Ù†ÛŒÙ…
      return this.findByNationalCode(createUserDto.nationalCode);
    } catch (error) {
      console.error('Error creating user:', error);
      throw error;
    }
  }
  


  // Ø¯Ø±ÛŒØ§ÙØª Ù„ÛŒØ³Øª ØªÙ…Ø§Ù…ÛŒ Ú©Ø§Ø±Ø¨Ø±Ø§Ù†
  async findAll() {
    return this.prisma.user.findMany({
      include: { role: true },
    });
  }

  // Ù¾ÛŒØ¯Ø§ Ú©Ø±Ø¯Ù† ÛŒÚ© Ú©Ø§Ø±Ø¨Ø± Ø¨Ø± Ø§Ø³Ø§Ø³ ID
  async findOne(id: number) {
    const user = await this.prisma.user.findUnique({
      where: { id },
      include: { role: true },
    });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  // Ù¾ÛŒØ¯Ø§ Ú©Ø±Ø¯Ù† Ú©Ø§Ø±Ø¨Ø± Ø¨Ø± Ø§Ø³Ø§Ø³ Ú©Ø¯ Ù…Ù„ÛŒ
  async findByNationalCode(nationalCode: string) {
    const user = await this.prisma.user.findUnique({
      where: { nationalCode },
      include: { role: true },
    });
    
    // Ø§Ú¯Ø± Ú©Ø§Ø±Ø¨Ø± Ù¾ÛŒØ¯Ø§ Ù†Ø´Ø¯ Ø¨Ø§ Ø§Ø³ØªÙØ§Ø¯Ù‡ Ø§Ø² Ú©ÙˆØ¦Ø±ÛŒ Ø®Ø§Ù… Ø¯ÙˆØ¨Ø§Ø±Ù‡ ØªÙ„Ø§Ø´ Ù…ÛŒâ€ŒÚ©Ù†ÛŒÙ…
    if (!user) {
      try {
        // Ø§Ø³ØªÙØ§Ø¯Ù‡ Ø§Ø² Ú©ÙˆØ¦Ø±ÛŒ Ø®Ø§Ù… Ø¨Ø±Ø§ÛŒ Ù¾ÛŒØ¯Ø§ Ú©Ø±Ø¯Ù† Ú©Ø§Ø±Ø¨Ø± Ø¨Ø§ Ú©Ø¯ Ù…Ù„ÛŒ
        const result = await this.prisma.$queryRaw`
          SELECT * FROM \`User\` WHERE nationalCode = ${nationalCode} LIMIT 1
        `;
        
        if (Array.isArray(result) && result.length > 0) {
          return result[0];
        }
        
        throw new NotFoundException('User not found');
      } catch (error) {
        console.error('Error finding user by national code:', error);
        throw error;
      }
    }
    
    return user;
  }

  // ÙˆÛŒØ±Ø§ÛŒØ´ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ú©Ø§Ø±Ø¨Ø±
  async update(id: number, updateUserDto: UpdateUserDto) {
    const userExists = await this.prisma.user.findUnique({
      where: { id },
    });
    if (!userExists) throw new NotFoundException('User not found');

    // Ø§Ú¯Ø± Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ø¬Ø¯ÛŒØ¯ Ø¯Ø§Ø¯Ù‡ Ø´Ø¯Ù‡ØŒ Ø¢Ù† Ø±Ø§ Ù‡Ø´ Ú©Ù†ÛŒØ¯
    const hashedPassword = updateUserDto.password ? await bcrypt.hash(updateUserDto.password, 10) : userExists.password;

    return await this.prisma.user.update({
      where: { id },
      data: {
        fullName: updateUserDto.fullName,
        nationalCode: updateUserDto.nationalCode,
        phoneNumber: updateUserDto.phoneNumber,
        password: hashedPassword, // Ø°Ø®ÛŒØ±Ù‡ Ú©Ø±Ø¯Ù† Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ù‡Ø´â€ŒØ´Ø¯Ù‡
        roleId: updateUserDto.roleId,
      },
    });
  }

  // Ø­Ø°Ù Ú©Ø§Ø±Ø¨Ø± Ø¨Ø± Ø§Ø³Ø§Ø³ ID
  async remove(id: number) {
    const userExists = await this.prisma.user.findUnique({
      where: { id },
    });
    if (!userExists) throw new NotFoundException('User not found');

    return await this.prisma.user.delete({
      where: { id },
    });
  }

  // Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù†Ù‚Ø´ Ú©Ø§Ø±Ø¨Ø±
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

  // Ø¯Ø±ÛŒØ§ÙØª ID Ù†Ù‚Ø´ Ø¨Ø± Ø§Ø³Ø§Ø³ Ù†Ø§Ù…
  async getRoleIdByName(roleName: RoleEnum): Promise<number> {
    const role = await this.prisma.role.findUnique({
      where: { name: roleName },
    });
    if (!role) throw new NotFoundException('Role not found'); // Ø§Ø¶Ø§ÙÙ‡ Ú©Ø±Ø¯Ù† Ø®Ø·Ø§ Ø¯Ø± ØµÙˆØ±Øª Ø¹Ø¯Ù… ÙˆØ¬ÙˆØ¯ Ù†Ù‚Ø´
    return role.id;
  }
}

